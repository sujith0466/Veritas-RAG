"""Authentication and user profile inspection routes.

Provides endpoints for inspecting current authentication state (`/status`)
and retrieving authenticated user profiles (`/me`).
"""

import datetime
import json
import secrets
import uuid

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.auth import (
    AuthStatusResponse,
    ChangePasswordCompleteRequest,
    ChangePasswordRequest,
    ChangePasswordVerifyCodeRequest,
    ChangePasswordVerifyCodeResponse,
    DemoRoleResetResponse,
    DemoRoleSwitchRequest,
    DemoRoleSwitchResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordResetCompleteRequest,
    PasswordResetVerifyResponse,
    ResetPasswordOTPRequest,
    ResetPasswordRequest,
    UserContext,
    VerifyOTPRequest,
)
from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.api.v1.schemas.registration import RegistrationRequest, RegistrationResponse
from backend.api.v1.schemas.verification import ResendVerificationRequest
from backend.api.v1.schemas.workspace_onboarding import (
    JoinIntentCreateData,
    JoinIntentCreateRequest,
    JoinIntentCreateResponse,
    JoinIntentPreviewData,
    JoinIntentPreviewResponse,
    JoiningMode,
)
from backend.cache.client import get_redis_client
from backend.core.dependencies.auth import get_current_user, get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.rate_limit import RateLimit
from backend.core.config import get_settings
from backend.core.exceptions.auth import AuthenticationException
from backend.services.auth.auth_service import AuthService
from backend.services.auth.email_verification_service import EmailVerificationService
from backend.services.auth.password_reset_service import PasswordResetService
from backend.services.auth.registration_service import RegistrationService
from backend.services.auth.sso_service import get_sso_provider
from backend.services.email.provider import get_email_provider

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Helper to construct standard ResponseMetadata for envelopes."""
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)

@router.post(
    "/register",
    status_code=201,
    response_model=SuccessResponse[RegistrationResponse],
    summary="Register a new user",
    description="Registers a new user account. Returns generic success to prevent email enumeration.",
    dependencies=[Depends(RateLimit("register", 10, 3600))],  # AUTH-011: 10/hr per IP
)
async def register(
    request: Request,
    payload: RegistrationRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RegistrationResponse]:
    """Register a new user in the system."""
    service = RegistrationService(db)
    await service.register_user(payload)

    return SuccessResponse(
        success=True,
        data=RegistrationResponse(),
        metadata=_build_metadata(request),
    )

@router.get(
    "/verify",
    response_model=SuccessResponse[dict],
    summary="Verify email address",
)
async def verify_email(
    request: Request,
    email: str,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Verify a user's email address using a token."""
    service = EmailVerificationService(db)
    await service.verify_token(email, token)
    return SuccessResponse(
        success=True,
        data={"message": "Email successfully verified"},
        metadata=_build_metadata(request),
    )

@router.post(
    "/resend-verification",
    response_model=SuccessResponse[dict],
    summary="Resend verification email",
)
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Resends a verification email (returns generic success to prevent enumeration)."""
    service = EmailVerificationService(db)
    raw_token = await service.generate_and_store_token(payload.email)

    if raw_token:
        email_provider = get_email_provider()
        await email_provider.send_verification_email(payload.email, raw_token)

    return SuccessResponse(
        success=True,
        data={"message": "If that email exists, a verification link has been sent."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/login",
    response_model=SuccessResponse[LoginResponse],
    summary="Login user",
    dependencies=[Depends(RateLimit("login", 20, 300))],
)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[LoginResponse]:
    """Authenticate and issue JWT + Refresh Token cookie."""
    service = AuthService(db)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    access_token, raw_refresh_token = await service.login(
        payload.email, payload.password, user_agent, ip_address
    )

    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=settings.security.cookie_secure,
        samesite="strict",
        path="/api/v1/auth/refresh"
    )

    return SuccessResponse(
        success=True,
        data=LoginResponse(access_token=access_token),
        metadata=_build_metadata(request),
    )

@router.post(
    "/logout",
    response_model=SuccessResponse[dict],
    summary="Logout user",
)
async def logout(
    request: Request,
    response: Response,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Logout user, revoke token, clear refresh cookie."""
    service = AuthService(db)
    jti = request.state.token_payload.jti if hasattr(request.state, "token_payload") else None
    exp = request.state.token_payload.exp if hasattr(request.state, "token_payload") else 0

    # AUTH-012: also revoke the refresh token so it cannot be replayed after logout
    raw_refresh_token = request.cookies.get("refresh_token")

    if jti:
        await service.logout(
            jti=jti,
            exp=exp,
            user_id=user.id,
            raw_refresh_token=raw_refresh_token,
        )

    # Clear any demo simulation state if this was a demo user
    settings = get_settings()
    if (
        settings.features.demo_role_switcher_enabled
        and settings.features.demo_account_user_id
        and str(user.id).strip().lower() == str(settings.features.demo_account_user_id).strip().lower()
    ):
        redis = get_redis_client()
        if redis:
            family_id = getattr(getattr(request.state, "token_payload", None), "family_id", None)
            if family_id:
                await redis.delete(f"auth:demo_session:family:{family_id}:simulated_role")
                await redis.delete(f"auth:demo_session:family:{family_id}:simulated_workspace_id")
            await redis.delete(f"auth:demo_session:user:{user.id}:simulated_role")
            await redis.delete(f"auth:demo_session:user:{user.id}:simulated_workspace_id")

    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")

    return SuccessResponse(
        success=True,
        data={"message": "Logged out successfully"},
        metadata=_build_metadata(request),
    )


@router.post(
    "/forgot-password",
    response_model=SuccessResponse[dict],
    summary="Request password reset",
    dependencies=[Depends(RateLimit("forgot-password", 3, 3600))],
)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Request a password reset email."""
    service = PasswordResetService(db)
    await service.generate_and_send_reset_token(payload.email)

    return SuccessResponse(
        success=True,
        data={"message": "If that email exists, a password reset link has been sent."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse[dict],
    summary="Reset password",
    dependencies=[Depends(RateLimit("reset-password", 5, 300))],
)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Reset password using a token."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    caller_context = {
        "user_agent": user_agent,
        "ip_address": ip_address,
        "path": "PASSWORD_RESET_TOKEN",
    }
    service = PasswordResetService(db)
    await service.reset_password(payload.token, payload.new_password, caller_context=caller_context)

    return SuccessResponse(
        success=True,
        data={"message": "Password successfully reset. You can now log in."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password-reset/request",
    response_model=SuccessResponse[dict],
    summary="Request recovery code for password reset",
    dependencies=[Depends(RateLimit("password-reset-request", 5, 3600))],
)
@router.post(
    "/password/otp/request",
    response_model=SuccessResponse[dict],
    summary="Request OTP for password reset (alias)",
    dependencies=[Depends(RateLimit("password-otp-request", 5, 3600))],
)
async def request_password_reset_code(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Request a password recovery code dispatched via email."""
    service = PasswordResetService(db)
    await service.request_recovery_code(payload.email)

    return SuccessResponse(
        success=True,
        data={"message": "If an account matches this email, a 6-digit verification code has been dispatched."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password-reset/verify",
    response_model=SuccessResponse[PasswordResetVerifyResponse],
    summary="Verify recovery code and issue ephemeral reset token",
    dependencies=[Depends(RateLimit("password-reset-verify", 5, 300))],
)
async def verify_password_reset_code(
    request: Request,
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[PasswordResetVerifyResponse]:
    """Verify 6-digit recovery code and return one-time 256-bit CSPRNG reset token."""
    service = PasswordResetService(db)
    reset_token = await service.verify_recovery_code(payload.email, payload.otp)

    return SuccessResponse(
        success=True,
        data=PasswordResetVerifyResponse(reset_token=reset_token, expires_in_seconds=900),
        metadata=_build_metadata(request),
    )


@router.post(
    "/password/otp/verify",
    response_model=SuccessResponse[dict],
    summary="Verify OTP (legacy alias)",
    dependencies=[Depends(RateLimit("password-otp-verify", 5, 300))],
)
async def verify_password_otp_legacy(
    request: Request,
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Legacy OTP verification endpoint."""
    service = PasswordResetService(db)
    reset_token = await service.verify_recovery_code(payload.email, payload.otp)

    return SuccessResponse(
        success=True,
        data={"message": "OTP verified successfully.", "reset_token": reset_token},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password-reset/complete",
    response_model=SuccessResponse[dict],
    summary="Complete password reset using reset token",
    dependencies=[Depends(RateLimit("password-reset-complete", 5, 300))],
)
async def complete_password_reset(
    request: Request,
    payload: PasswordResetCompleteRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Complete password reset using verified ephemeral reset token."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    caller_context = {
        "user_agent": user_agent,
        "ip_address": ip_address,
        "path": "PASSWORD_RESET_RECOVERY",
    }
    service = PasswordResetService(db)
    await service.complete_password_reset(
        payload.email, payload.reset_token, payload.new_password, caller_context=caller_context
    )

    return SuccessResponse(
        success=True,
        data={"message": "Password successfully reset. You can now log in with your new password."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password/otp/reset",
    response_model=SuccessResponse[dict],
    summary="Reset password via OTP (legacy alias)",
)
async def reset_password_with_otp_legacy(
    request: Request,
    payload: ResetPasswordOTPRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Reset password directly using OTP (legacy alias)."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    caller_context = {
        "user_agent": user_agent,
        "ip_address": ip_address,
        "path": "PASSWORD_RESET_OTP",
    }
    service = PasswordResetService(db)
    await service.reset_password_with_otp(
        payload.email, payload.otp, payload.new_password, caller_context=caller_context
    )

    return SuccessResponse(
        success=True,
        data={"message": "Password successfully reset. You can now log in."},
        metadata=_build_metadata(request),
    )



@router.post(
    "/change-password",
    response_model=SuccessResponse[dict],
    summary="Change password with current password (Path A)",
    description="Authenticates current password, updates to new password, rotates current session, and revokes other sessions.",
    dependencies=[Depends(RateLimit("change-password", 5, 300))],
)
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Authenticated password change with current password verification (Path A)."""
    token_payload = getattr(request.state, "token_payload", None)
    current_jti = getattr(token_payload, "jti", None)
    current_exp = getattr(token_payload, "exp", 0)
    family_id = getattr(token_payload, "family_id", None)

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    caller_context = {
        "current_jti": current_jti,
        "current_exp": current_exp,
        "user_agent": user_agent,
        "ip_address": ip_address,
    }

    service = PasswordResetService(db)
    access_token, raw_refresh_token = await service.change_password(
        user_id=user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        caller_family_id=family_id,
        caller_context=caller_context,
    )

    # Set HTTP-only refresh token cookie for session continuity
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=settings.security.cookie_secure,
        samesite="strict",
        path="/api/v1/auth/refresh",
    )

    return SuccessResponse(
        success=True,
        data={
            "message": "Password changed successfully.",
            "access_token": access_token,
        },
        metadata=_build_metadata(request),
    )


@router.post(
    "/change-password/request-code",
    response_model=SuccessResponse[dict],
    summary="Request security code for password change",
    description="Dispatches a 6-digit verification code to the authenticated user's email address.",
)
async def request_change_password_code(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Request 6-digit security code sent to registered email for password change."""
    service = PasswordResetService(db)
    await service.request_security_code(user.id)
    return SuccessResponse(
        success=True,
        data={"message": "Security verification code sent to your registered email address."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/change-password/verify-code",
    response_model=SuccessResponse[ChangePasswordVerifyCodeResponse],
    summary="Verify security code for password change",
    description="Verifies the 6-digit security code and returns an ephemeral change token.",
)
async def verify_change_password_code(
    request: Request,
    payload: ChangePasswordVerifyCodeRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ChangePasswordVerifyCodeResponse]:
    """Verify 6-digit security code and obtain ephemeral change token."""
    service = PasswordResetService(db)
    change_token = await service.verify_security_code(user.id, payload.code)
    return SuccessResponse(
        success=True,
        data=ChangePasswordVerifyCodeResponse(change_token=change_token, expires_in_seconds=900),
        metadata=_build_metadata(request),
    )


@router.post(
    "/change-password/complete",
    response_model=SuccessResponse[dict],
    summary="Complete password change with security token (Path B)",
    description="Updates password using the verified change token, rotates current session, and revokes other sessions.",
    dependencies=[Depends(RateLimit("change-password-complete", 5, 300))],
)
async def complete_change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordCompleteRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Complete password change using verified change token (Path B)."""
    token_payload = getattr(request.state, "token_payload", None)
    current_jti = getattr(token_payload, "jti", None)
    current_exp = getattr(token_payload, "exp", 0)
    family_id = getattr(token_payload, "family_id", None)

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    caller_context = {
        "current_jti": current_jti,
        "current_exp": current_exp,
        "user_agent": user_agent,
        "ip_address": ip_address,
    }

    service = PasswordResetService(db)
    access_token, raw_refresh_token = await service.complete_password_change(
        user_id=user.id,
        change_token=payload.change_token,
        new_password=payload.new_password,
        caller_family_id=family_id,
        caller_context=caller_context,
    )

    # Set HTTP-only refresh token cookie for session continuity
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=settings.security.cookie_secure,
        samesite="strict",
        path="/api/v1/auth/refresh",
    )

    return SuccessResponse(
        success=True,
        data={
            "message": "Password changed successfully.",
            "access_token": access_token,
        },
        metadata=_build_metadata(request),
    )


@router.get(
    "/me",
    response_model=SuccessResponse[UserContext],
    summary="Get current user profile",
    description="Returns the authenticated UserContext of the calling user.",
)
async def get_me(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> SuccessResponse[UserContext]:
    """Return the currently authenticated user profile."""
    return SuccessResponse(
        success=True,
        data=user,
        metadata=_build_metadata(request),
    )


@router.get(
    "/status",
    response_model=SuccessResponse[AuthStatusResponse],
    summary="Get authentication status",
    description="Returns whether the request is authenticated and optional user summary.",
)
async def get_status(
    request: Request,
    user: UserContext | None = Depends(get_optional_user),
) -> SuccessResponse[AuthStatusResponse]:
    """Inspect current authentication status without requiring a valid token."""
    return SuccessResponse(
        success=True,
        data=AuthStatusResponse(
            is_authenticated=user is not None,
            user=user,
        ),
        metadata=_build_metadata(request),
    )


@router.post(
    "/refresh",
    response_model=SuccessResponse[LoginResponse],
    summary="Rotate refresh token",
)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[LoginResponse]:
    """Rotate refresh token and issue new access token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    service = AuthService(db)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    # Rotate refresh token
    access_token, new_raw_refresh = await service.rotate_refresh_token(
        raw_refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip_address
    )

    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=settings.security.cookie_secure,
        samesite="strict",
        path="/api/v1/auth/refresh"
    )

    return SuccessResponse(
        success=True,
        data=LoginResponse(access_token=access_token),
        metadata=_build_metadata(request),
    )


@router.post(
    "/demo-switch-role",
    response_model=SuccessResponse[DemoRoleSwitchResponse],
    summary="Switch demo role simulation (Authorized Demo User Only)",
    description="Simulates a target role for the designated demo operator without mutating persistent database records.",
)
async def demo_switch_role(
    request: Request,
    payload: DemoRoleSwitchRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[DemoRoleSwitchResponse]:
    """Dynamically switch simulated demo role for authorized demo user without DB mutations."""
    settings = get_settings()
    if not settings.features.demo_role_switcher_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo role switcher is disabled in this environment.",
        )

    if (
        not settings.features.demo_account_user_id
        or str(current_user.id).strip().lower() != str(settings.features.demo_account_user_id).strip().lower()
    ):
        logger.warning(
            "Unauthorized demo role switch attempt",
            actor_user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: User is not authorized to use the demo role switcher.",
        )

    target_role = payload.target_role.strip().lower()
    valid_roles = {"platform_admin", "owner", "admin", "member", "viewer"}
    if target_role not in valid_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid target role '{payload.target_role}'. Valid roles: {sorted(list(valid_roles))}",
        )

    # Tightened PLATFORM_ADMIN simulation safeguards
    if target_role == "platform_admin":
        if not settings.features.demo_allow_platform_admin_simulation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PLATFORM_ADMIN simulation is disabled in this environment.",
            )
        resolved_ws = None
    else:
        resolved_ws = payload.workspace_id or current_user.tenant_id or current_user.workspace_id

    from backend.core.security.jwt import get_jwt_service
    jwt_service = get_jwt_service()

    token_payload = getattr(request.state, "token_payload", None)
    current_jti = getattr(token_payload, "jti", None)
    current_exp = getattr(token_payload, "exp", 0)
    family_id = getattr(token_payload, "family_id", None) or str(uuid.uuid4())

    # Revoke old access token
    if current_jti and current_exp:
        await jwt_service.revoke_token(current_jti, current_exp)

    # Store simulation state in Redis with 3600s TTL
    redis = get_redis_client()
    if redis:
        # Family-scoped key
        if family_id:
            await redis.set(f"auth:demo_session:family:{family_id}:simulated_role", target_role, ex=3600)
            if resolved_ws:
                await redis.set(f"auth:demo_session:family:{family_id}:simulated_workspace_id", str(resolved_ws), ex=3600)
            else:
                await redis.set(f"auth:demo_session:family:{family_id}:simulated_workspace_id", "none", ex=3600)

        # User-scoped fallback key
        await redis.set(f"auth:demo_session:user:{current_user.id}:simulated_role", target_role, ex=3600)
        if resolved_ws:
            await redis.set(f"auth:demo_session:user:{current_user.id}:simulated_workspace_id", str(resolved_ws), ex=3600)
        else:
            await redis.set(f"auth:demo_session:user:{current_user.id}:simulated_workspace_id", "none", ex=3600)

    from backend.models.entities.user import User
    user_entity = await db.get(User, current_user.id)
    if not user_entity or not user_entity.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    # Issue fresh simulated JWT
    access_token, _, _ = await jwt_service.issue_tokens(
        user=user_entity,
        session=db,
        workspace_id=resolved_ws,
        role=target_role,
        family_id=family_id,
        demo_simulated=True,
    )

    logger.info(
        "Demo role switched successfully",
        actor_user_id=str(current_user.id),
        simulated_role=target_role,
        workspace_id=str(resolved_ws) if resolved_ws else None,
    )

    return SuccessResponse(
        success=True,
        data=DemoRoleSwitchResponse(
            access_token=access_token,
            role=target_role,
            workspace_id=str(resolved_ws) if resolved_ws else None,
            demo_simulated=True,
        ),
        metadata=_build_metadata(request),
    )


@router.post(
    "/demo-reset-role",
    response_model=SuccessResponse[DemoRoleResetResponse],
    summary="Reset demo role to authentic baseline (Authorized Demo User Only)",
    description="Terminates active demo role simulation and restores the authentic database role and active workspace context.",
)
async def demo_reset_role(
    request: Request,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[DemoRoleResetResponse]:
    """Reset simulated demo role back to authentic database role."""
    settings = get_settings()
    if not settings.features.demo_role_switcher_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo role switcher is disabled in this environment.",
        )

    if (
        not settings.features.demo_account_user_id
        or str(current_user.id).strip().lower() != str(settings.features.demo_account_user_id).strip().lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: User is not authorized to use the demo role switcher.",
        )

    from backend.core.security.jwt import get_jwt_service
    jwt_service = get_jwt_service()

    token_payload = getattr(request.state, "token_payload", None)
    current_jti = getattr(token_payload, "jti", None)
    current_exp = getattr(token_payload, "exp", 0)
    family_id = getattr(token_payload, "family_id", None)

    # Revoke old simulated token
    if current_jti and current_exp:
        await jwt_service.revoke_token(current_jti, current_exp)

    # Clear Redis simulation state
    redis = get_redis_client()
    if redis:
        if family_id:
            await redis.delete(f"auth:demo_session:family:{family_id}:simulated_role")
            await redis.delete(f"auth:demo_session:family:{family_id}:simulated_workspace_id")
        await redis.delete(f"auth:demo_session:user:{current_user.id}:simulated_role")
        await redis.delete(f"auth:demo_session:user:{current_user.id}:simulated_workspace_id")

    from backend.models.entities.user import User
    user_entity = await db.get(User, current_user.id)
    if not user_entity or not user_entity.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    # Issue authentic baseline token
    access_token, _, resolved_family = await jwt_service.issue_tokens(
        user=user_entity,
        session=db,
        family_id=family_id,
        demo_simulated=False,
    )

    # Verify newly issued token to inspect resulting baseline role and workspace
    new_payload = await jwt_service.verify_token(access_token)

    logger.info(
        "Demo role reset to baseline successfully",
        actor_user_id=str(current_user.id),
        base_role=new_payload.role,
        workspace_id=new_payload.workspace_id,
    )

    return SuccessResponse(
        success=True,
        data=DemoRoleResetResponse(
            access_token=access_token,
            role=new_payload.role,
            workspace_id=new_payload.workspace_id,
            demo_simulated=False,
            message="Reset to authentic database role successfully",
        ),
        metadata=_build_metadata(request),
    )


def _get_validated_frontend_url() -> str:
    """Validate FRONTEND_URL against approved origin policy."""
    import os
    import urllib.parse

    raw_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
    if not raw_url:
        return "http://localhost:5173"

    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        logger.warning("Unsafe FRONTEND_URL configured, falling back to default", url=raw_url)
        return "http://localhost:5173"

    return raw_url


@router.post(
    "/join-intent",
    response_model=JoinIntentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record pre-authentication join intent",
)
async def create_join_intent(
    payload: JoinIntentCreateRequest,
) -> JoinIntentCreateResponse:
    """Stores a pre-auth join intent in Redis with a 600-second TTL.

    Returns an opaque intent_id that can be attached to the SSO redirect or frontend session.
    """
    redis = get_redis_client()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session cache unavailable. Unable to create join intent.",
        )

    intent_id = secrets.token_urlsafe(32)
    session_data = {
        "intent_id": intent_id,
        "workspace_id": payload.workspace_id,
        "join_code": payload.join_code,
        "invitation_token": payload.invitation_token,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    await redis.set(f"auth:join_intent:{intent_id}", json.dumps(session_data), ex=600)

    return JoinIntentCreateResponse(
        success=True,
        message="Join intent recorded successfully.",
        data=JoinIntentCreateData(
            intent_id=intent_id,
            expires_in_seconds=600,
        ),
    )


@router.get(
    "/join-intent/{intent_id}",
    response_model=JoinIntentPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve safe pre-auth join intent preview",
)
async def get_join_intent_preview(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
) -> JoinIntentPreviewResponse:
    """Resolves safe public preview metadata for a join intent without leaking secrets."""
    redis = get_redis_client()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session cache unavailable.",
        )

    raw_data = await redis.get(f"auth:join_intent:{intent_id}")
    if not raw_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join intent not found or expired.",
        )

    intent = json.loads(raw_data)
    workspace_id = intent.get("workspace_id")
    join_code = intent.get("join_code")
    invitation_token = intent.get("invitation_token")

    target_name = None
    target_slug = None
    target_public_id = None
    joining_mode = JoiningMode.OPEN
    requires_code = False
    has_invitation = False
    target_email_masked = None

    from backend.repositories.workspace import WorkspaceRepository
    from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
    from backend.services.workspace.invitation_service import parse_invitation_token, verify_invitation_secret

    ws_repo = WorkspaceRepository(db)

    if invitation_token:
        has_invitation = True
        joining_mode = JoiningMode.INVITE_ONLY
        inv_repo = WorkspaceInvitationRepository(db)
        selector, secret = parse_invitation_token(invitation_token)
        inv = None
        if selector:
            inv = await inv_repo.get_by_token_selector(selector)
        if inv and verify_invitation_secret(secret, inv.token_hash):
            ws = await ws_repo.get_by_id(inv.workspace_id)
            if ws:
                target_name = ws.name
                target_slug = ws.slug
                target_public_id = ws.public_id
            if inv.email and "@" in inv.email:
                parts = inv.email.split("@")
                masked_user = parts[0][0] + "***" if parts[0] else "***"
                target_email_masked = f"{masked_user}@{parts[1]}"

    if workspace_id and not target_public_id:
        ws = await ws_repo.get_by_public_id(workspace_id.upper())
        if not ws:
            ws = await ws_repo.get_by_slug(workspace_id.lower())
        if ws:
            target_name = ws.name
            target_slug = ws.slug
            target_public_id = ws.public_id

    if join_code:
        joining_mode = JoiningMode.JOIN_CODE
        requires_code = True

    return JoinIntentPreviewResponse(
        success=True,
        message="Join intent preview retrieved successfully.",
        data=JoinIntentPreviewData(
            intent_id=intent_id,
            workspace_id=target_public_id or workspace_id,
            workspace_name=target_name,
            workspace_slug=target_slug,
            joining_mode=joining_mode,
            requires_join_code=requires_code,
            has_invitation=has_invitation,
            target_email_masked=target_email_masked,
        ),
    )


@router.get(
    "/sso/login/{provider}",
    summary="Initiate SSO login",
)
async def sso_login(
    provider: str,
    intent_id: str | None = Query(None, description="Pre-created server-side join intent ID"),
) -> RedirectResponse:
    """Redirect to SSO provider's authorization URL, preserving join intent via opaque reference only."""
    join_intent = None

    if intent_id:
        redis = get_redis_client()
        if redis:
            raw_intent = await redis.get(f"auth:join_intent:{intent_id}")
            if raw_intent:
                join_intent = json.loads(raw_intent)

    sso_service = get_sso_provider(provider)
    auth_url = await sso_service.get_auth_url(join_intent=join_intent)
    return RedirectResponse(url=auth_url)


@router.get(
    "/sso/callback/{provider}",
    summary="SSO Callback",
)
async def sso_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle OIDC callback and redirect to frontend."""
    frontend_url = _get_validated_frontend_url()

    try:
        sso_service = get_sso_provider(provider)
        profile = await sso_service.exchange_code(code, state)
        join_intent = profile.get("join_intent")

        # Replay protection: atomically purge pre-auth intent cache if intent_id was used
        if join_intent and isinstance(join_intent, dict) and join_intent.get("intent_id"):
            redis = get_redis_client()
            if redis:
                from backend.services.auth.sso_service import atomic_consume_state
                await atomic_consume_state(redis, f"auth:join_intent:{join_intent['intent_id']}")

        auth_service = AuthService(db)
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        access_token, raw_refresh_token = await auth_service.handle_oidc_login(
            email=profile["email"],
            provider=profile["provider"],
            provider_user_id=profile["provider_user_id"],
            metadata=profile,
            user_agent=user_agent,
            ip_address=ip_address,
            join_intent=join_intent,
        )

        # Set the refresh token cookie on the redirect response
        settings = get_settings()
        redirect_resp = RedirectResponse(url=f"{frontend_url}/auth/callback#access_token={access_token}")
        redirect_resp.set_cookie(
            key="refresh_token",
            value=raw_refresh_token,
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            secure=settings.security.cookie_secure,
            samesite="strict",
            path="/api/v1/auth/refresh"
        )

        return redirect_resp

    except AuthenticationException as e:
        logger.warning("SSO Callback failed", error=str(e))
        return RedirectResponse(url=f"{frontend_url}/auth/login?error=sso_failed")
    except Exception as e:
        logger.error("SSO Callback unexpected error", error=str(e))
        raise HTTPException(status_code=503, detail="SSO provider unavailable or unconfigured.")
