"""Unit and Service tests for PasswordResetService."""

import datetime
import hashlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from backend.core.exceptions.auth import AuthenticationException
from backend.core.security.password import get_password_hash, verify_password
from backend.database.engine import get_session_factory
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.models.entities.user_session import UserSession
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.auth.password_reset_service import PasswordResetService, _mask_email


async def create_test_user_fixture():
    session_factory = get_session_factory()
    unique_email = f"recovery_user_{uuid.uuid4().hex[:8]}@example.com"
    initial_password = "OldPassword123!"
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    rand_hex = uuid.uuid4().hex[:6]

    async with session_factory() as session:
        user = User(
            id=user_id,
            email=unique_email,
            hashed_password=get_password_hash(initial_password),
            is_active=True,
            is_verified=True,
            role="member",
        )
        session.add(user)

        workspace = Workspace(
            id=workspace_id,
            name=f"WS_{rand_hex}",
            slug=f"ws-{rand_hex}",
            public_id=f"pub_{rand_hex}",
            storage_prefix=f"sp_{rand_hex}",
            qdrant_namespace=f"qn_{rand_hex}",
        )
        session.add(workspace)

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceRole.MEMBER.value,
            status=MemberStatus.ACTIVE.value,
        )
        session.add(member)

        user_sess = UserSession(
            user_id=user_id,
            family_id=str(uuid.uuid4()),
            refresh_token_hash=f"fake_hash_{uuid.uuid4().hex}",
            is_revoked=False,
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7),
        )
        session.add(user_sess)
        await session.commit()

    return {
        "id": user_id,
        "email": unique_email,
        "password": initial_password,
        "workspace_id": workspace_id,
    }


async def cleanup_test_user(user_id: uuid.UUID, workspace_id: uuid.UUID):
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM password_recovery_otps WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspace_members WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspaces WHERE id = :wid"), {"wid": workspace_id})
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await session.commit()


def test_mask_email_utility():
    assert _mask_email("u@example.com") == "u***@example.com"
    assert _mask_email("user@veritas.rag") == "u***@veritas.rag"
    assert _mask_email("john.doe@company.org") == "j***@company.org"
    assert _mask_email("invalid") == "***"


@pytest.mark.asyncio
async def test_request_otp_success_dispatches_email():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])
                assert mock_provider.send_otp_email.call_count == 1
                call_email, raw_otp = mock_provider.send_otp_email.call_args[0]
                assert call_email == user["email"]
                assert len(raw_otp) == 6
                assert raw_otp.isdigit()

            # Check DB for OTP entry
            stmt = select(PasswordRecoveryOTP).where(PasswordRecoveryOTP.user_id == user["id"])
            res = await session.execute(stmt)
            otp = res.scalars().first()
            assert otp is not None
            assert not otp.is_used
            assert not otp.is_invalidated
            assert otp.attempts == 0
            assert hashlib.sha256(raw_otp.encode()).hexdigest() == otp.otp_hash

            # Check Audit Log
            stmt_audit = select(AuditLog).where(
                AuditLog.user_id == user["id"],
                AuditLog.action == "password_reset.requested"
            )
            audit_res = await session.execute(stmt_audit)
            audit = audit_res.scalars().first()
            assert audit is not None
            assert audit.status == "success"
            assert audit.details["channel"] == "EMAIL"
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_request_otp_unknown_email_generic_response_dummy_processing():
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = PasswordResetService(session)
        unknown_email = f"unknown_{uuid.uuid4().hex[:8]}@example.com"

        # Should not raise exception
        await service.request_recovery_code(unknown_email)


@pytest.mark.asyncio
async def test_request_otp_cooldown_and_velocity_limits_on_email_hash():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            # First call succeeds
            await service.request_recovery_code(user["email"])

            # Second immediate call should trigger cooldown 429
            with pytest.raises(HTTPException) as exc_info:
                await service.request_recovery_code(user["email"])
            assert exc_info.value.status_code == 429
            assert "Please wait" in str(exc_info.value.detail)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_verify_otp_valid_returns_reset_token():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])
                _, raw_otp = mock_provider.send_otp_email.call_args[0]

            # Verify code
            reset_token = await service.verify_recovery_code(user["email"], raw_otp)
            assert reset_token is not None
            assert len(reset_token) >= 32

            # Check user entity has reset token hash
            user_stmt = select(User).where(User.id == user["id"])
            user_res = await session.execute(user_stmt)
            u = user_res.scalar_one()
            assert u.password_reset_token_hash == hashlib.sha256(reset_token.encode()).hexdigest()
            assert u.password_reset_token_expires_at is not None

            # Check audit log
            stmt_audit = select(AuditLog).where(
                AuditLog.user_id == user["id"],
                AuditLog.action == "password_reset.verified"
            )
            audit_res = await session.execute(stmt_audit)
            assert audit_res.scalars().first() is not None
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_verify_otp_invalid_increments_attempts():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])

            with pytest.raises(AuthenticationException):
                await service.verify_recovery_code(user["email"], "000000")

            # Check attempt count incremented
            otp_stmt = select(PasswordRecoveryOTP).where(PasswordRecoveryOTP.user_id == user["id"])
            res = await session.execute(otp_stmt)
            otp = res.scalars().first()
            assert otp.attempts == 1
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_verify_otp_max_attempts_invalidates_code():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])

            # 5 failed attempts
            for _ in range(5):
                with pytest.raises(AuthenticationException):
                    await service.verify_recovery_code(user["email"], "000000")

            # 6th attempt should raise 429
            with pytest.raises(HTTPException) as exc_info:
                await service.verify_recovery_code(user["email"], "000000")
            assert exc_info.value.status_code == 429

            otp_stmt = select(PasswordRecoveryOTP).where(PasswordRecoveryOTP.user_id == user["id"])
            res = await session.execute(otp_stmt)
            otp = res.scalars().first()
            assert otp.is_invalidated is True
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_complete_reset_valid_token_updates_password_revokes_sessions():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])
                _, raw_otp = mock_provider.send_otp_email.call_args[0]

            reset_token = await service.verify_recovery_code(user["email"], raw_otp)

            new_password = "BrandNewPassword456!"
            await service.complete_password_reset(user["email"], reset_token, new_password)

            # Verify password changed
            user_stmt = select(User).where(User.id == user["id"])
            user_res = await session.execute(user_stmt)
            u = user_res.scalar_one()
            assert verify_password(new_password, u.hashed_password)
            assert not verify_password(user["password"], u.hashed_password)
            assert u.password_reset_token_hash is None
            assert u.password_reset_token_expires_at is None

            # Verify user sessions revoked
            sess_stmt = select(UserSession).where(UserSession.user_id == user["id"])
            sess_res = await session.execute(sess_stmt)
            user_sess = sess_res.scalars().first()
            assert user_sess.is_revoked is True

            # Verify audit log completed
            stmt_audit = select(AuditLog).where(
                AuditLog.user_id == user["id"],
                AuditLog.action == "password_reset.completed"
            )
            audit_res = await session.execute(stmt_audit)
            assert audit_res.scalars().first() is not None
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_complete_reset_invalid_or_consumed_token_fails():
    user = await create_test_user_fixture()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            service = PasswordResetService(session)

            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                await service.request_recovery_code(user["email"])
                _, raw_otp = mock_provider.send_otp_email.call_args[0]

            reset_token = await service.verify_recovery_code(user["email"], raw_otp)
            await service.complete_password_reset(user["email"], reset_token, "FirstNewPassword123!")

            # Second attempt with consumed token must fail
            with pytest.raises(AuthenticationException):
                await service.complete_password_reset(user["email"], reset_token, "SecondNewPassword123!")
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])
