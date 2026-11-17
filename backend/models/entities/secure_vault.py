"""Secure Vault Entities for Batch 3 Cryptographic Compliance Nonces & Redaction.

Governed by Section 7 Batch 3 (WP 7.12, CR-B3-45, CR-B3-46).
Mapped to tables in schema `secure_vault`.
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database.base import Base


class OfficerSigningKey(Base):
    """Officer public signing key registered for compliance operations."""

    __tablename__ = "officer_signing_keys"
    __table_args__ = {"schema": "secure_vault"}

    officer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    public_key = Column(LargeBinary, nullable=False)
    key_algorithm = Column(String(32), nullable=False, default="Ed25519")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    officer = relationship("User", foreign_keys=[officer_id])


class ActionNonce(Base):
    """One-time action nonce issued for compliance redaction tickets."""

    __tablename__ = "action_nonces"
    __table_args__ = {"schema": "secure_vault"}

    nonce_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(String(64), nullable=False, default="COMPLIANCE_REDACTION")
    target_id = Column(UUID(as_uuid=True), nullable=False)
    officer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("secure_vault.officer_signing_keys.officer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    consumed_txid = Column(BigInteger, nullable=True)

    officer_key = relationship("OfficerSigningKey", foreign_keys=[officer_id])


class RedactionExecutionFence(Base):
    """Relational execution fence armed during compliance redaction procedure."""

    __tablename__ = "redaction_execution_fence"
    __table_args__ = {"schema": "secure_vault"}

    txid = Column(BigInteger, primary_key=True)
    transfer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_ownership_transfers.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    nonce_id = Column(
        UUID(as_uuid=True),
        ForeignKey("secure_vault.action_nonces.nonce_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    action = Column(String(64), nullable=False, default="COMPLIANCE_REDACTION")
    officer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("secure_vault.officer_signing_keys.officer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    nonce = relationship("ActionNonce", foreign_keys=[nonce_id])
    transfer = relationship("WorkspaceOwnershipTransfer", foreign_keys=[transfer_id])
    officer_key = relationship("OfficerSigningKey", foreign_keys=[officer_id])
