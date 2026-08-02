"""Password Recovery OTP Entity Model.

Tracks active and historical Email OTPs for password recovery.
"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel
from backend.models.entities.user import User


class PasswordRecoveryOTP(BaseModel):
    """Tracks Email OTPs for password recovery."""

    __tablename__ = "password_recovery_otps"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="EMAIL", nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow
    )
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_invalidated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PasswordRecoveryOTP(id={self.id}, user_id={self.user_id}, is_used={self.is_used}, is_invalidated={self.is_invalidated})>"
