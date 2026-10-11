"""User Privacy Data Export Service.

Extracts user profile, workspace memberships, user preferences, and notification records.
Strictly scrubs password hashes, salts, reset tokens, MFA secrets, and API credentials.
"""

import uuid
from typing import Any
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.user import User
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace import Workspace
from backend.models.entities.notification import Notification

FORBIDDEN_EXPORT_KEYS = {
    "hashed_password",
    "password_hash",
    "salt",
    "secret_hash",
    "encrypted_secret",
    "verification_token_hash",
    "password_reset_token_hash",
    "refresh_token_hash",
    "otp_hash",
    "secret_key",
    "token",
}


def _scrub_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively removes sensitive keys from dictionaries."""
    if not data or not isinstance(data, dict):
        return {}
    cleaned = {}
    for k, v in data.items():
        if k.lower() in FORBIDDEN_EXPORT_KEYS:
            continue
        if isinstance(v, dict):
            cleaned[k] = _scrub_dict(v)
        elif isinstance(v, list):
            cleaned[k] = [_scrub_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned


class DataExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_user_export(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Compiles and scrubs user data archive."""
        # 1. Fetch User Record
        user_stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        user = (await self.session.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise ValueError("User not found or account is deactivated.")

        # 2. Fetch Workspace Memberships
        memberships_stmt = (
            select(WorkspaceMember, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id, WorkspaceMember.is_deleted == False)
        )
        membership_rows = (await self.session.execute(memberships_stmt)).all()

        workspaces_data = []
        for member, ws_name in membership_rows:
            workspaces_data.append({
                "workspace_id": str(member.workspace_id),
                "workspace_name": ws_name,
                "role": member.role,
                "status": member.status,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "metadata": _scrub_dict(member.member_metadata),
            })

        # 3. Fetch Recent In-App Notifications
        notif_stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.is_deleted == False)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
        notifications = (await self.session.execute(notif_stmt)).scalars().all()

        notifications_data = []
        for n in notifications:
            notifications_data.append({
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "severity": n.severity,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            })

        # 4. Construct Clean Export Payload
        export_payload = {
            "export_metadata": {
                "format_version": "1.0",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "exported_user_id": str(user.id),
            },
            "profile": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "avatar_url": user.avatar_url,
                "timezone": user.timezone,
                "language": user.language,
                "theme_preference": user.theme_preference,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "profile_data": _scrub_dict(user.profile_data),
            },
            "preferences": _scrub_dict(user.preferences),
            "workspace_memberships": workspaces_data,
            "recent_notifications": notifications_data,
        }

        return export_payload
