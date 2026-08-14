"""Authentication and user profile inspection routes.

Provides endpoints for inspecting current authentication state (`/status`)
and retrieving authenticated user profiles (`/me`).
"""

import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.auth import (
    AuthStatusResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordOTPRequest,
    ResetPasswordRequest,
    UserContext,
    VerifyOTPRequest,
)
from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.api.v1.schemas.registration import RegistrationRequest, RegistrationResponse
from backend.api.v1.schemas.verification import ResendVerificationRequest
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
        secure=settings.app.environment == "production",
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
    service = PasswordResetService(db)
    await service.reset_password(payload.token, payload.new_password)

    return SuccessResponse(
        success=True,
        data={"message": "Password successfully reset. You can now log in."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password/otp/request",
    response_model=SuccessResponse[dict],
    summary="Request OTP for password reset",
    dependencies=[Depends(RateLimit("password-otp-request", 3, 3600))],
)
async def request_password_otp(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Request a password reset OTP via email."""
    service = PasswordResetService(db)
    await service.request_otp(payload.email)

    return SuccessResponse(
        success=True,
        data={"message": "If that email exists, an OTP has been sent."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password/otp/verify",
    response_model=SuccessResponse[dict],
    summary="Verify OTP",
    dependencies=[Depends(RateLimit("password-otp-verify", 5, 300))],
)
async def verify_password_otp(
    request: Request,
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Verify an OTP."""
    service = PasswordResetService(db)
    await service.verify_otp(payload.email, payload.otp)

    return SuccessResponse(
        success=True,
        data={"message": "OTP verified successfully."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/password/otp/reset",
    response_model=SuccessResponse[dict],
    summary="Reset password via OTP",
)
async def reset_password_with_otp(
    request: Request,
    payload: ResetPasswordOTPRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Reset password using an OTP."""
    service = PasswordResetService(db)
    await service.reset_password_with_otp(payload.email, payload.otp, payload.new_password)

    return SuccessResponse(
        success=True,
        data={"message": "Password successfully reset. You can now log in."},
        metadata=_build_metadata(request),
    )


@router.post(
    "/change-password",
    response_model=SuccessResponse[dict],
    summary="Change password (authenticated)",
    description="Verifies the current password then updates to the new password, revoking all active sessions.",
)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Authenticated password change — requires valid JWT and current password."""
    service = PasswordResetService(db)
    await service.change_password(user.id, payload.current_password, payload.new_password)

    return SuccessResponse(
        success=True,
        data={"message": "Password updated successfully. Please log in again."},
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
        secure=settings.app.environment == "production",
        samesite="strict",
        path="/api/v1/auth/refresh"
    )

    return SuccessResponse(
        success=True,
        data=LoginResponse(access_token=access_token),
        metadata=_build_metadata(request),
    )


@router.get(
    "/sso/login/{provider}",
    summary="Initiate SSO login",
)
async def sso_login(
    provider: str,
) -> RedirectResponse:
    """Redirect to SSO provider's authorization URL."""
    sso_service = get_sso_provider(provider)
    auth_url = await sso_service.get_auth_url()
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
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    try:
        sso_service = get_sso_provider(provider)
        profile = await sso_service.exchange_code(code, state)

        auth_service = AuthService(db)
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        access_token, raw_refresh_token = await auth_service.handle_oidc_login(
            email=profile["email"],
            provider=profile["provider"],
            provider_user_id=profile["provider_user_id"],
            metadata=profile,
            user_agent=user_agent,
            ip_address=ip_address
        )

        # Set the refresh token cookie
        settings = get_settings()
        response.set_cookie(
            key="refresh_token",
            value=raw_refresh_token,
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            secure=settings.app.environment == "production",
            samesite="strict",
            path="/api/v1/auth/refresh"
        )

        return RedirectResponse(url=f"{frontend_url}/auth/callback#access_token={access_token}")

    except AuthenticationException as e:
        logger.warning("SSO Callback failed", error=str(e))
        return RedirectResponse(url=f"{frontend_url}/auth/login?error=sso_failed")
    except Exception as e:
        logger.error("SSO Callback unexpected error", error=str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="SSO provider unavailable or unconfigured.")
