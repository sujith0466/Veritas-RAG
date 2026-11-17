"""Personal-Data Compliance Redaction Service.

Governed by Section 7 Batch 3 (WP 7.12, CR-B3-37 through CR-B3-41, CR-B3-86).
Encapsulates cryptographic ticket generation and stored procedure execution for
GDPR/CCPA personal data redaction on workspace ownership transfers.
"""

from datetime import UTC, datetime
from typing import Any, Optional
import uuid

from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)

# Canonical v2 Ticket Constants
MAGIC_HEADER = b"\x56\x52\x41\x47"  # 0x56524147 ("VRAG")
TICKET_VERSION = 2
ACTION_STRING = b"COMPLIANCE_REDACTION"
PAYLOAD_LENGTH = 92
SIGNATURE_LENGTH = 64
TICKET_LENGTH = 156


class ComplianceRedactionService:
    """Service orchestrating compliance nonce issuance, ticket signing, and redaction execution."""

    @staticmethod
    def build_ticket_payload(
        nonce_id: uuid.UUID,
        officer_id: uuid.UUID,
        transfer_id: uuid.UUID,
        bitmask: int,
        issued_at: datetime,
        expires_at: datetime,
    ) -> bytes:
        """
        Build the canonical 92-byte binary v2 payload (CR-B3-41).
        Layout:
        - 0..3: Magic Header 0x56524147 (4 bytes)
        - 4: Version (1 byte, value=2)
        - 5: Action Length (1 byte, value=20)
        - 6..25: Action String b'COMPLIANCE_REDACTION' (20 bytes)
        - 26..41: Nonce UUID bytes (16 bytes)
        - 42..57: Officer UUID bytes (16 bytes)
        - 58..73: Target Transfer UUID bytes (16 bytes)
        - 74: Redaction Bitmask (1 byte, 1|2|4|8)
        - 75..82: Issued At Milliseconds Big-Endian (8 bytes)
        - 83..90: Expires At Milliseconds Big-Endian (8 bytes)
        - 91: Reserved / Zero-Padding (1 byte)
        """
        if (bitmask & 240) != 0:
            raise ValueError("Reserved bits in bitmask must be zero (bits 4-7)")
        if (bitmask & 15) == 0:
            raise ValueError("Bitmask must specify at least one field (bits 0-3 non-zero)")

        magic = MAGIC_HEADER
        ver = bytes([TICKET_VERSION])
        act_len = bytes([len(ACTION_STRING)])
        act = ACTION_STRING
        nonce_b = nonce_id.bytes if isinstance(nonce_id, uuid.UUID) else uuid.UUID(str(nonce_id)).bytes
        officer_b = officer_id.bytes if isinstance(officer_id, uuid.UUID) else uuid.UUID(str(officer_id)).bytes
        target_b = transfer_id.bytes if isinstance(transfer_id, uuid.UUID) else uuid.UUID(str(transfer_id)).bytes
        mask = bytes([bitmask])
        issued_ms = int(issued_at.timestamp() * 1000).to_bytes(8, "big")
        expires_ms = int(expires_at.timestamp() * 1000).to_bytes(8, "big")
        pad = b"\x00"

        payload = magic + ver + act_len + act + nonce_b + officer_b + target_b + mask + issued_ms + expires_ms + pad
        if len(payload) != PAYLOAD_LENGTH:
            raise ValueError(f"Payload length must be exactly {PAYLOAD_LENGTH} bytes, got {len(payload)}")
        return payload

    @classmethod
    def sign_ticket(
        cls,
        payload: bytes,
        private_key: ed25519.Ed25519PrivateKey | bytes,
    ) -> bytes:
        """Sign canonical 92-byte payload with Ed25519 and produce 156-byte signed ticket."""
        if len(payload) != PAYLOAD_LENGTH:
            raise ValueError(f"Payload must be {PAYLOAD_LENGTH} bytes")
        if isinstance(private_key, bytes):
            key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        else:
            key_obj = private_key
        signature = key_obj.sign(payload)
        ticket = payload + signature
        if len(ticket) != TICKET_LENGTH:
            raise ValueError(f"Signed ticket must be {TICKET_LENGTH} bytes")
        return ticket

    @staticmethod
    async def issue_compliance_nonce(
        session: AsyncSession,
        transfer_id: uuid.UUID,
        officer_id: uuid.UUID,
        ttl_seconds: int = 120,
    ) -> tuple[uuid.UUID, datetime]:
        """
        Invoke secure_vault.sp_issue_compliance_nonce stored procedure.
        Must be executed in authorized session (raguard_auth_worker or sec_admin).
        """
        stmt = text("""
            CALL secure_vault.sp_issue_compliance_nonce(
                :action, :target_id, :officer_id, :ttl, NULL, NULL
            );
        """)
        result = await session.execute(
            stmt,
            {
                "action": "COMPLIANCE_REDACTION",
                "target_id": str(transfer_id),
                "officer_id": str(officer_id),
                "ttl": ttl_seconds,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve issued nonce from stored procedure",
            )
        nonce_id, expires_at = row
        return nonce_id, expires_at

    @staticmethod
    async def execute_compliance_redaction(
        session: AsyncSession,
        signed_ticket: bytes,
        officer_pubkey: bytes,
        transfer_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Invoke secure_vault.sp_execute_compliance_redaction stored procedure.
        Must be executed in compliance session (raguard_compliance or sec_admin).
        """
        if len(signed_ticket) != TICKET_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Signed ticket length must be exactly {TICKET_LENGTH} bytes, got {len(signed_ticket)}",
            )
        if len(officer_pubkey) != 32:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Officer public key must be exactly 32 bytes, got {len(officer_pubkey)}",
            )

        stmt = text("""
            CALL secure_vault.sp_execute_compliance_redaction(
                :signed_ticket, :officer_pubkey, :transfer_id
            );
        """)
        await session.execute(
            stmt,
            {
                "signed_ticket": signed_ticket,
                "officer_pubkey": officer_pubkey,
                "transfer_id": str(transfer_id),
            },
        )

        logger.info(
            "Successfully executed compliance personal data redaction",
            transfer_id=str(transfer_id),
        )
        return {
            "status": "SUCCESS",
            "transfer_id": str(transfer_id),
            "executed_at": datetime.now(UTC).isoformat(),
        }
