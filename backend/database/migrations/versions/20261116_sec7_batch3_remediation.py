"""section 7 batch 3 targeted defect remediation

Revision ID: 20261116_sec7_batch3_remediation
Revises: 20261115_sec7_batch3_final
Create Date: 2026-11-16 08:35:00.000000

VRAG-AUTH-SEC7-BATCH3-STAGEC-DEFECT-CLOSURE-20261116-01:
- F-B3-AUDIT-01: Transfer schema secure_vault ownership to sec_admin
- F-B3-AUDIT-02: Correct 4-byte magic header comparison in sp_execute_compliance_redaction
- F-B3-AUDIT-03: Align public.audit_logs insert statement and privileges with actual schema
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261116_sec7_batch3_remediation"
down_revision = "20261115_sec7_batch3_final"
branch_labels = None
depends_on = None

PROCEDURE_SQL_COMPLIANCE_REDACTION = r"""
CREATE OR REPLACE PROCEDURE secure_vault.sp_execute_compliance_redaction(
    IN p_signed_ticket BYTEA,
    IN p_officer_pubkey BYTEA,
    IN p_transfer_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, secure_vault, pgsodium
AS $$
DECLARE
    v_payload BYTEA;
    v_sig BYTEA;
    v_magic BYTEA;
    v_version INT;
    v_action_len INT;
    v_action_str TEXT;
    v_nonce_id UUID;
    v_officer_id UUID;
    v_target_id UUID;
    v_bitmask INT;
    v_issued_at_ms BIGINT;
    v_expires_at_ms BIGINT;
    v_expires_at TIMESTAMPTZ;
    v_nonce_rec RECORD;
    v_rows_affected INT;
    v_key_revoked TIMESTAMPTZ;
    v_transfer_rec RECORD;
    v_already_redacted BOOLEAN;
BEGIN
    -- 1. Structural Pre-flight Checks (CR-B3-41)
    IF pg_catalog.octet_length(p_signed_ticket) <> 156 THEN
        RAISE EXCEPTION 'Cryptographic Error: Signed ticket length must be exactly 156 bytes (92 payload + 64 sig), received %', pg_catalog.octet_length(p_signed_ticket)
            USING ERRCODE = '22023';
    END IF;

    IF pg_catalog.octet_length(p_officer_pubkey) <> 32 THEN
        RAISE EXCEPTION 'Cryptographic Error: Officer public key must be exactly 32 bytes, received %', pg_catalog.octet_length(p_officer_pubkey)
            USING ERRCODE = '22023';
    END IF;

    IF p_transfer_id IS NULL THEN
        RAISE EXCEPTION 'Invocation Error: Target transfer_id cannot be null'
            USING ERRCODE = '22023';
    END IF;

    -- 2. Extract Payload (92 bytes) and Signature (64 bytes)
    v_payload := pg_catalog.substring(p_signed_ticket, 1, 92);
    v_sig     := pg_catalog.substring(p_signed_ticket, 93, 64);

    -- 3. Parse Canonical Payload Offsets (CR-B3-41)
    v_magic         := pg_catalog.substring(v_payload, 1, 4);
    v_version       := pg_catalog.get_byte(v_payload, 4);
    v_action_len    := pg_catalog.get_byte(v_payload, 5);

    IF v_magic <> '\x56524147'::BYTEA THEN
        RAISE EXCEPTION 'Cryptographic Error: Invalid ticket magic header % (expected 0x56524147)', v_magic
            USING ERRCODE = '22023';
    END IF;

    IF v_version <> 2 THEN
        RAISE EXCEPTION 'Cryptographic Error: Unsupported ticket format version % (expected v2)', v_version
            USING ERRCODE = '22023';
    END IF;

    IF v_action_len <> 20 THEN
        RAISE EXCEPTION 'Cryptographic Error: Invalid action length % (expected 20)', v_action_len
            USING ERRCODE = '22023';
    END IF;

    v_action_str    := pg_catalog.convert_from(pg_catalog.substring(v_payload, 7, 20), 'UTF8');
    IF v_action_str <> 'COMPLIANCE_REDACTION' THEN
        RAISE EXCEPTION 'Cryptographic Error: Unknown ticket action "%" (expected "COMPLIANCE_REDACTION")', v_action_str
            USING ERRCODE = '22023';
    END IF;

    -- Extract UUIDs
    v_nonce_id      := (pg_catalog.encode(pg_catalog.substring(v_payload, 27, 16), 'hex'))::uuid;
    v_officer_id    := (pg_catalog.encode(pg_catalog.substring(v_payload, 43, 16), 'hex'))::uuid;
    v_target_id     := (pg_catalog.encode(pg_catalog.substring(v_payload, 59, 16), 'hex'))::uuid;

    -- Extract Bitmask
    v_bitmask       := pg_catalog.get_byte(v_payload, 74);
    IF (v_bitmask & 240) <> 0 THEN
        RAISE EXCEPTION 'Cryptographic Error: Reserved bits in redaction bitmask must be zero, found %', (v_bitmask & 240)
            USING ERRCODE = '22023';
    END IF;
    IF (v_bitmask & 15) = 0 THEN
        RAISE EXCEPTION 'Cryptographic Error: Redaction bitmask must specify at least one field (bits 0-3 non-zero)'
            USING ERRCODE = '22023';
    END IF;

    -- Extract Timestamps (Big-Endian Milliseconds)
    v_issued_at_ms  := (pg_catalog.get_byte(v_payload, 75)::BIGINT << 56) |
                       (pg_catalog.get_byte(v_payload, 76)::BIGINT << 48) |
                       (pg_catalog.get_byte(v_payload, 77)::BIGINT << 40) |
                       (pg_catalog.get_byte(v_payload, 78)::BIGINT << 32) |
                       (pg_catalog.get_byte(v_payload, 79)::BIGINT << 24) |
                       (pg_catalog.get_byte(v_payload, 80)::BIGINT << 16) |
                       (pg_catalog.get_byte(v_payload, 81)::BIGINT << 8)  |
                       (pg_catalog.get_byte(v_payload, 82)::BIGINT);

    v_expires_at_ms := (pg_catalog.get_byte(v_payload, 83)::BIGINT << 56) |
                       (pg_catalog.get_byte(v_payload, 84)::BIGINT << 48) |
                       (pg_catalog.get_byte(v_payload, 85)::BIGINT << 40) |
                       (pg_catalog.get_byte(v_payload, 86)::BIGINT << 32) |
                       (pg_catalog.get_byte(v_payload, 87)::BIGINT << 24) |
                       (pg_catalog.get_byte(v_payload, 88)::BIGINT << 16) |
                       (pg_catalog.get_byte(v_payload, 89)::BIGINT << 8)  |
                       (pg_catalog.get_byte(v_payload, 90)::BIGINT);

    v_expires_at    := pg_catalog.to_timestamp(v_expires_at_ms / 1000.0);

    -- 4. Ticket Expiry & Temporal Verification (CR-B3-41)
    IF pg_catalog.clock_timestamp() > v_expires_at THEN
        RAISE EXCEPTION 'Authentication Error: Action ticket expired at % (current: %)', v_expires_at, pg_catalog.clock_timestamp()
            USING ERRCODE = '42501';
    END IF;

    -- 5. Ticket-to-Target UUID Invariance Assertion (CR-B3-38)
    IF v_target_id <> p_transfer_id THEN
        RAISE EXCEPTION 'Binding Error: Ticket target_id % does not match target transfer_id %', v_target_id, p_transfer_id
            USING ERRCODE = '42501';
    END IF;

    -- 6. Verify Ed25519 Detached Signature via pgsodium (CR-B3-39)
    IF NOT pgsodium.crypto_sign_verify_detached(v_sig, v_payload, p_officer_pubkey) THEN
        RAISE EXCEPTION 'Cryptographic Error: Detached Ed25519 signature verification failed'
            USING ERRCODE = '42501';
    END IF;

    -- 7. Officer Public Key Registration & Immediate Revocation Check (CR-B3-53, CR-B3-90)
    -- Acquire FOR SHARE lock on signing key (Layer 7.1 L_KEY in Global Lock Hierarchy)
    -- This serializes against concurrent key revocation (UPDATE ... FOR UPDATE)
    SELECT revoked_at INTO v_key_revoked
    FROM secure_vault.officer_signing_keys
    WHERE officer_id = v_officer_id AND public_key = p_officer_pubkey
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Authentication Error: Public key not registered for officer %', v_officer_id
            USING ERRCODE = '42501';
    END IF;

    IF v_key_revoked IS NOT NULL THEN
        RAISE EXCEPTION 'Authentication Error: Officer signing key was revoked at %', v_key_revoked
            USING ERRCODE = '42501';
    END IF;

    -- 8. Nonce Validation, Expiry Consistency & Atomic Single-Use Consumption (CR-B3-85, CR-B3-86)
    SELECT nonce_id, action, target_id, officer_id, expires_at, consumed_at
    INTO v_nonce_rec
    FROM secure_vault.action_nonces
    WHERE nonce_id = v_nonce_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Authentication Error: Nonce % does not exist in registry', v_nonce_id
            USING ERRCODE = '42501';
    END IF;

    IF v_nonce_rec.consumed_at IS NOT NULL THEN
        RAISE EXCEPTION 'Replay Violation: Nonce % has already been consumed at %', v_nonce_id, v_nonce_rec.consumed_at
            USING ERRCODE = '42501';
    END IF;

    IF v_nonce_rec.action <> 'COMPLIANCE_REDACTION' OR v_nonce_rec.target_id <> p_transfer_id OR v_nonce_rec.officer_id <> v_officer_id THEN
        RAISE EXCEPTION 'Binding Error: Nonce attributes (action, target, officer) do not match authorization ticket'
            USING ERRCODE = '42501';
    END IF;

    IF pg_catalog.clock_timestamp() > v_nonce_rec.expires_at THEN
        RAISE EXCEPTION 'Authentication Error: Nonce % expired at %', v_nonce_id, v_nonce_rec.expires_at
            USING ERRCODE = '42501';
    END IF;

    -- Nonce DB expiry vs ticket expiry consistency (within 1 second) (CR-B3-41)
    IF pg_catalog.abs(EXTRACT(EPOCH FROM (v_nonce_rec.expires_at - v_expires_at))) > 1.0 THEN
        RAISE EXCEPTION 'Binding Error: Nonce expiry % differs from ticket expiry % by more than 1s', v_nonce_rec.expires_at, v_expires_at
            USING ERRCODE = '22023';
    END IF;

    -- Atomic conditional nonce consumption (CR-B3-85)
    UPDATE secure_vault.action_nonces
    SET consumed_at = pg_catalog.clock_timestamp(),
        consumed_txid = pg_catalog.txid_current()
    WHERE nonce_id = v_nonce_id
      AND consumed_at IS NULL;

    GET DIAGNOSTICS v_rows_affected = ROW_COUNT;
    IF v_rows_affected <> 1 THEN
        RAISE EXCEPTION 'Replay or Concurrency Violation: Nonce % has already been consumed or concurrent execution conflict', v_nonce_id
            USING ERRCODE = '42501';
    END IF;

    -- 9. Check Transfer Record & Target Fields Prior to Update (CR-B3-38)
    SELECT id, workspace_id, current_owner_email_snapshot, nominated_user_email_snapshot, response_notes, decision_notes
    INTO v_transfer_rec
    FROM public.workspace_ownership_transfers
    WHERE id = p_transfer_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Target Error: Transfer record % does not exist', p_transfer_id
            USING ERRCODE = '02000';
    END IF;

    -- Assert target fields are not already completely redacted
    v_already_redacted := TRUE;
    IF (v_bitmask & 1) <> 0 AND v_transfer_rec.current_owner_email_snapshot <> '[REDACTED_PII]' THEN
        v_already_redacted := FALSE;
    END IF;
    IF (v_bitmask & 2) <> 0 AND v_transfer_rec.nominated_user_email_snapshot <> '[REDACTED_PII]' THEN
        v_already_redacted := FALSE;
    END IF;
    IF (v_bitmask & 4) <> 0 AND v_transfer_rec.response_notes IS NOT NULL AND v_transfer_rec.response_notes <> '[REDACTED_PII]' THEN
        v_already_redacted := FALSE;
    END IF;
    IF (v_bitmask & 8) <> 0 AND v_transfer_rec.decision_notes IS NOT NULL AND v_transfer_rec.decision_notes <> '[REDACTED_PII]' THEN
        v_already_redacted := FALSE;
    END IF;

    IF v_already_redacted THEN
        RAISE EXCEPTION 'Redaction Redundancy: All selected fields for transfer % are already redacted', p_transfer_id
            USING ERRCODE = '55000';
    END IF;

    -- 10. Arm Relational Execution Fence (CR-B3-86, CR-B3-88, CR-B3-89)
    INSERT INTO secure_vault.redaction_execution_fence (
        txid, transfer_id, nonce_id, action, officer_id, created_at
    ) VALUES (
        pg_catalog.txid_current(), p_transfer_id, v_nonce_id, 'COMPLIANCE_REDACTION', v_officer_id, pg_catalog.clock_timestamp()
    );

    -- 11. Execute Authorized Column-Level Redaction
    UPDATE public.workspace_ownership_transfers
    SET
        current_owner_email_snapshot = CASE WHEN (v_bitmask & 1) <> 0 THEN '[REDACTED_PII]' ELSE current_owner_email_snapshot END,
        nominated_user_email_snapshot = CASE WHEN (v_bitmask & 2) <> 0 THEN '[REDACTED_PII]' ELSE nominated_user_email_snapshot END,
        response_notes                = CASE WHEN (v_bitmask & 4) <> 0 AND response_notes IS NOT NULL THEN '[REDACTED_PII]' ELSE response_notes END,
        decision_notes                = CASE WHEN (v_bitmask & 8) <> 0 AND decision_notes IS NOT NULL THEN '[REDACTED_PII]' ELSE decision_notes END
    WHERE id = p_transfer_id;

    GET DIAGNOSTICS v_rows_affected = ROW_COUNT;
    IF v_rows_affected <> 1 THEN
        RAISE EXCEPTION 'Execution Error: Expected 1 row updated, updated %', v_rows_affected
            USING ERRCODE = '02000';
    END IF;

    -- 12. Write Immutable Audit Log Entry
    INSERT INTO public.audit_logs (
        id, action, tenant_id, user_id, resource_type, resource_id, details, status, created_at
    ) VALUES (
        pg_catalog.gen_random_uuid(),
        'COMPLIANCE_PERSONAL_DATA_REDACTION',
        v_transfer_rec.workspace_id,
        v_officer_id,
        'workspace_ownership_transfers',
        p_transfer_id::TEXT,
        jsonb_build_object(
            'action', 'COMPLIANCE_REDACTION',
            'nonce_id', v_nonce_id,
            'bitmask', v_bitmask,
            'redacted_fields', jsonb_build_object(
                'current_owner_email_snapshot', (v_bitmask & 1) <> 0,
                'nominated_user_email_snapshot', (v_bitmask & 2) <> 0,
                'response_notes', (v_bitmask & 4) <> 0,
                'decision_notes', (v_bitmask & 8) <> 0
            ),
            'execution_txid', pg_catalog.txid_current(),
            'executed_at', pg_catalog.clock_timestamp()
        ),
        'SUCCESS',
        pg_catalog.clock_timestamp()
    );
END;
$$;
"""


def upgrade():
    # 1. F-B3-AUDIT-01: Transfer schema secure_vault ownership to sec_admin
    op.execute("ALTER SCHEMA secure_vault OWNER TO sec_admin;")

    # 2. F-B3-AUDIT-02 & F-B3-AUDIT-03: Recompile sp_execute_compliance_redaction
    op.execute(PROCEDURE_SQL_COMPLIANCE_REDACTION)

    # 3. Re-affirm ownership and execute privilege grants
    op.execute("ALTER PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) OWNER TO sec_admin;")
    op.execute("REVOKE ALL ON PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) FROM PUBLIC, raguard_app, raguard_auth_worker;")
    op.execute("GRANT EXECUTE ON PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) TO raguard_compliance;")

    # 4. Re-affirm audit_logs privileges for sec_admin
    op.execute("""
        GRANT INSERT, SELECT (id, action, tenant_id, user_id, resource_type, resource_id, details, status, created_at)
        ON public.audit_logs TO sec_admin;
    """)


def downgrade():
    # 1. Revert schema ownership to t3b_test_admin
    op.execute("ALTER SCHEMA secure_vault OWNER TO t3b_test_admin;")
