"""Section 7 Batch 3 Final Migration: Departure History, Redaction Engine & WORM Protection

Revision ID: 20261115_sec7_batch3_final
Revises: 20261115_sec7_batch2_lifecycle
Create Date: 2026-11-15 12:00:00.000000

Controlling Documents:
- SECTION_6_SECTION_7_COMBINED_IMPLEMENTATION_PLAN.md (Rev 4.14)
- SECTION_7_BATCH_3_INTEGRATED_IMPLEMENTATION_PLAN.md (Revision 2.12, Baseline: Revision 2.11)
- Project Owner Decisions: POD-V410-01, PO-D32-01, PO-D32-03, Q12, Q13, Q15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261115_sec7_batch3_final"
down_revision = "20261115_sec7_batch2_lifecycle"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# SQL String Constants (Self-Contained In-Line Definitions) (CR-B3-48)
# ---------------------------------------------------------------------------

PREFLIGHT_ASSERTION_SQL = """
DO $$
BEGIN
    -- 1. Server encoding check
    IF current_setting('server_encoding') <> 'UTF8' THEN
        RAISE EXCEPTION 'Pre-Flight Error: PostgreSQL server encoding must be UTF8, found "%"', current_setting('server_encoding')
            USING ERRCODE = '08000';
    END IF;

    -- 2. pgsodium extension availability check
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgsodium') THEN
        RAISE EXCEPTION 'Pre-Flight Error: Extension "pgsodium" is not installed in database'
            USING ERRCODE = '0A000';
    END IF;

    -- 3. Required extension functions check
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p 
        JOIN pg_namespace n ON n.oid = p.pronamespace 
        WHERE n.nspname = 'pgsodium' AND p.proname = 'crypto_sign_verify_detached'
    ) THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required function pgsodium.crypto_sign_verify_detached is missing'
            USING ERRCODE = '0A000';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p 
        JOIN pg_namespace n ON n.oid = p.pronamespace 
        WHERE n.nspname = 'pgsodium' AND p.proname = 'randombytes_buf'
    ) THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required function pgsodium.randombytes_buf is missing'
            USING ERRCODE = '0A000';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p 
        JOIN pg_namespace n ON n.oid = p.pronamespace 
        WHERE n.nspname = 'pgsodium' AND p.proname = 'crypto_generichash'
    ) THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required function pgsodium.crypto_generichash is missing'
            USING ERRCODE = '0A000';
    END IF;

    -- 4. Role prerequisites check
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sec_admin') THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required role "sec_admin" does not exist'
            USING ERRCODE = '42704';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raguard_auth_worker') THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required role "raguard_auth_worker" does not exist'
            USING ERRCODE = '42704';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raguard_compliance') THEN
        RAISE EXCEPTION 'Pre-Flight Error: Required role "raguard_compliance" does not exist'
            USING ERRCODE = '42704';
    END IF;
END $$;
"""


FUNCTION_SQL_FN_ENFORCE_DEPARTURE_WORM = """
CREATE OR REPLACE FUNCTION public.fn_enforce_former_owner_departure_worm()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'WORM Violation: Mutation of workspace former owner departure records is strictly prohibited under PO-D32-03'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'WORM Violation: Deletion of workspace former owner departure records is strictly prohibited under PO-D32-03'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;
"""

FUNCTION_SQL_FN_ENFORCE_TRANSFER_WORM = """
CREATE OR REPLACE FUNCTION public.fn_enforce_transfer_worm_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public, secure_vault
AS $$
DECLARE
    v_fence_nonce_id UUID;
    v_fence_action VARCHAR(64);
    v_fence_officer_id UUID;
BEGIN
    -- 1. Unconditional Prohibition of DELETE Statements
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'WORM Violation: Deletion of workspace ownership transfer records is strictly prohibited under PO-D32-03'
            USING ERRCODE = '55000';
    END IF;

    -- 2. Core Identity Invariants (Permanently Immutable Under All Circumstances)
    IF NEW.id IS DISTINCT FROM OLD.id OR
       NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR
       NEW.nominated_by_user_id IS DISTINCT FROM OLD.nominated_by_user_id OR
       NEW.nominee_user_id IS DISTINCT FROM OLD.nominee_user_id OR
       NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'WORM Violation: Core transfer identity attributes (id, workspace_id, nominated_by, nominee, created_at) are permanently immutable'
            USING ERRCODE = '55000';
    END IF;

    -- 3. Detect Compliance Redaction Branch (CR-B3-87)
    IF (NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot) OR
       (NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot) OR
       (NEW.response_notes = '[REDACTED_PII]' AND OLD.response_notes IS DISTINCT FROM NEW.response_notes) OR
       (NEW.decision_notes = '[REDACTED_PII]' AND OLD.decision_notes IS DISTINCT FROM NEW.decision_notes) THEN

        -- 3.1 Security Definer Execution Role Assertion (CR-B3-45, CR-B3-57)
        IF CURRENT_USER <> 'sec_admin' THEN
            RAISE EXCEPTION 'Authorization Violation: Compliance redaction requires sec_admin role context, received "%"', CURRENT_USER
                USING ERRCODE = '42501';
        END IF;

        -- 3.2 Atomic Single-Use Relational Fence Destruction (CR-B3-86, CR-B3-88, CR-B3-89)
        DELETE FROM secure_vault.redaction_execution_fence
        WHERE txid = pg_catalog.txid_current() 
          AND transfer_id = NEW.id
        RETURNING nonce_id, action, officer_id INTO v_fence_nonce_id, v_fence_action, v_fence_officer_id;

        IF v_fence_nonce_id IS NULL THEN
            RAISE EXCEPTION 'Authorization Violation: Missing or previously consumed execution fence for transfer % in txid %', NEW.id, pg_catalog.txid_current()
                USING ERRCODE = '42501';
        END IF;

        -- 3.3 Relational Ticket-to-Nonce-to-Fence Binding Verification (CR-B3-86, CR-B3-89)
        IF v_fence_action <> 'COMPLIANCE_REDACTION' THEN
            RAISE EXCEPTION 'Authorization Violation: Execution fence action "%" does not match required "COMPLIANCE_REDACTION"', v_fence_action
                USING ERRCODE = '42501';
        END IF;

        IF NOT EXISTS (
            SELECT 1 
            FROM secure_vault.action_nonces
            WHERE nonce_id = v_fence_nonce_id
              AND target_id = NEW.id
              AND action = 'COMPLIANCE_REDACTION'
              AND officer_id = v_fence_officer_id
              AND consumed_txid = pg_catalog.txid_current()
              AND consumed_at IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Authorization Violation: Nonce % is not bound to transfer % in txid %', v_fence_nonce_id, NEW.id, pg_catalog.txid_current()
                USING ERRCODE = '42501';
        END IF;

        -- 3.4 Exact Redaction Allowlist & Exhaustive Transition Verification (CR-B3-10, CR-B3-87)
        -- Email Snapshot 1: current_owner_email_snapshot
        IF NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot THEN
            IF OLD.current_owner_email_snapshot = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: current_owner_email_snapshot is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.current_owner_email_snapshot <> '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: current_owner_email_snapshot can only be mutated to "[REDACTED_PII]", received "%"', NEW.current_owner_email_snapshot
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        -- Email Snapshot 2: nominated_user_email_snapshot
        IF NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            IF OLD.nominated_user_email_snapshot = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: nominated_user_email_snapshot is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.nominated_user_email_snapshot <> '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: nominated_user_email_snapshot can only be mutated to "[REDACTED_PII]", received "%"', NEW.nominated_user_email_snapshot
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        -- Response Notes: response_notes
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            IF OLD.response_notes = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.response_notes IS NULL THEN
                RAISE EXCEPTION 'Redaction Precondition Error: Cannot redact response_notes when field is NULL'
                    USING ERRCODE = '22023';
            END IF;
            IF NEW.response_notes <> '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: response_notes can only be redacted to "[REDACTED_PII]", received "%"', NEW.response_notes
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        -- Decision Notes: decision_notes
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            IF OLD.decision_notes = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.decision_notes IS NULL THEN
                RAISE EXCEPTION 'Redaction Precondition Error: Cannot redact decision_notes when field is NULL'
                    USING ERRCODE = '22023';
            END IF;
            IF NEW.decision_notes <> '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: decision_notes can only be redacted to "[REDACTED_PII]", received "%"', NEW.decision_notes
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        -- 3.5 Absolute Invariance of All 17 Non-PII Fields Under Redaction (CR-B3-44)
        IF NEW.status IS DISTINCT FROM OLD.status OR
           NEW.rejection_reason IS DISTINCT FROM OLD.rejection_reason OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR
           NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_status IS DISTINCT FROM OLD.decision_status OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.decided_at IS DISTINCT FROM OLD.decided_at OR
           NEW.decided_by_user_id IS DISTINCT FROM OLD.decided_by_user_id THEN
            RAISE EXCEPTION 'WORM Violation: Non-PII transfer lifecycle fields cannot be modified during compliance redaction'
                USING ERRCODE = '55000';
        END IF;

        RETURN NEW;
    END IF;

    -- 4. Forward Lifecycle Transitions (9 Permitted Transitions) (CR-B3-44, CR-B3-87)

    -- Transition 1: PENDING -> CANCELLED
    IF OLD.status = 'PENDING' AND NEW.status = 'CANCELLED' THEN
        IF NEW.cancelled_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: CANCELLED status requires non-null cancelled_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS NOT NULL OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS NOT NULL OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_status IS NOT NULL OR NEW.decision_deadline_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during CANCELLED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 2: PENDING -> DECLINED
    IF OLD.status = 'PENDING' AND NEW.status = 'DECLINED' THEN
        IF NEW.responded_at IS NULL OR NEW.rejection_reason IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECLINED status requires non-null responded_at and rejection_reason'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        IF (OLD.response_notes IS NOT NULL AND NEW.response_notes IS DISTINCT FROM OLD.response_notes) THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.cancelled_at IS NOT NULL OR
           NEW.expired_at IS NOT NULL OR NEW.former_owner_choice IS NOT NULL OR
           NEW.former_owner_choice_at IS NOT NULL OR NEW.decision_status IS NOT NULL OR
           NEW.decision_deadline_at IS NOT NULL OR NEW.decided_at IS NOT NULL OR
           NEW.decided_by_user_id IS NOT NULL OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECLINED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 3: PENDING -> EXPIRED
    IF OLD.status = 'PENDING' AND NEW.status = 'EXPIRED' THEN
        IF NEW.expired_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: EXPIRED status requires non-null expired_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL OR
           NEW.former_owner_choice IS NOT NULL OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_status IS NOT NULL OR NEW.decision_deadline_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during EXPIRED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 4: PENDING -> REVOKED_BY_ADMIN
    IF OLD.status = 'PENDING' AND NEW.status = 'REVOKED_BY_ADMIN' THEN
        IF NEW.cancelled_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: REVOKED_BY_ADMIN requires non-null cancelled_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS NOT NULL OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS NOT NULL OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_status IS NOT NULL OR NEW.decision_deadline_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during REVOKED_BY_ADMIN transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 5: PENDING -> ACCEPTED & decision_status = PENDING
    IF OLD.status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.decision_status = 'PENDING' THEN
        IF NEW.responded_at IS NULL OR NEW.decision_deadline_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: ACCEPTED requires non-null responded_at and decision_deadline_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        IF (OLD.response_notes IS NOT NULL AND NEW.response_notes IS DISTINCT FROM OLD.response_notes) THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.cancelled_at IS NOT NULL OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS NOT NULL OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during ACCEPTED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 6: ACCEPTED & dec_status=PENDING -> CANCELLED_BY_NOMINEE
    IF OLD.status = 'ACCEPTED' AND OLD.decision_status = 'PENDING' AND NEW.status = 'CANCELLED_BY_NOMINEE' AND NEW.decision_status = 'CANCELLED' THEN
        IF NEW.cancelled_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: CANCELLED_BY_NOMINEE requires non-null cancelled_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        IF (OLD.response_notes IS NOT NULL AND NEW.response_notes IS DISTINCT FROM OLD.response_notes) THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.response_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS DISTINCT FROM OLD.responded_at OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS NOT NULL OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during CANCELLED_BY_NOMINEE transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 7: ACCEPTED & dec_status=PENDING -> DECIDED_RETAINED
    IF OLD.status = 'ACCEPTED' AND OLD.decision_status = 'PENDING' AND NEW.decision_status = 'DECIDED_RETAINED' THEN
        IF NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECIDED_RETAINED requires non-null decided_at and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.decision_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        IF (OLD.decision_notes IS NOT NULL AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes) THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.decision_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECIDED_RETAINED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 8: ACCEPTED & dec_status=PENDING -> DECIDED_REMOVED
    IF OLD.status = 'ACCEPTED' AND OLD.decision_status = 'PENDING' AND NEW.decision_status = 'DECIDED_REMOVED' THEN
        IF NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECIDED_REMOVED requires non-null decided_at and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.decision_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        IF (OLD.decision_notes IS NOT NULL AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes) THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.decision_notes = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECIDED_REMOVED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 9: ACCEPTED & dec_status=PENDING -> UNRESPONSIVE_TIMED_OUT
    IF OLD.status = 'ACCEPTED' AND OLD.decision_status = 'PENDING' AND NEW.decision_status = 'UNRESPONSIVE_TIMED_OUT' THEN
        IF NEW.decided_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: UNRESPONSIVE_TIMED_OUT requires non-null decided_at'
                USING ERRCODE = '22023';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.decided_by_user_id IS NOT NULL OR NEW.decision_notes IS NOT NULL OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during UNRESPONSIVE_TIMED_OUT transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- If no valid transition matched, reject update
    RAISE EXCEPTION 'WORM Violation: Mutation from status=%, choice=%, dec_status=% to status=%, choice=%, dec_status=% is strictly prohibited under PO-D32-03',
        OLD.status, OLD.former_owner_choice, OLD.decision_status, NEW.status, NEW.former_owner_choice, NEW.decision_status
        USING ERRCODE = '55000';
END;
$$;
"""

PROCEDURE_SQL_ISSUE_COMPLIANCE_NONCE = """
CREATE OR REPLACE PROCEDURE secure_vault.sp_issue_compliance_nonce(
    IN p_action TEXT,
    IN p_target_id UUID,
    IN p_officer_id UUID,
    IN p_ttl_seconds INTEGER,
    OUT p_nonce_id UUID,
    OUT p_expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, secure_vault
AS $$
DECLARE
    v_caller TEXT;
    v_key_valid BOOLEAN := FALSE;
BEGIN
    v_caller := SESSION_USER;
    IF NOT pg_catalog.pg_has_role(v_caller, 'auth_authority_role', 'MEMBER') AND v_caller <> 'sec_admin' THEN
        RAISE EXCEPTION 'Authorization Error: Caller "%" is not a member of auth_authority_role', v_caller
            USING ERRCODE = '42501';
    END IF;

    IF p_action <> 'COMPLIANCE_REDACTION' THEN
        RAISE EXCEPTION 'Invalid Action: Unsupported action "%"', p_action USING ERRCODE = '22023';
    END IF;

    IF p_ttl_seconds < 10 OR p_ttl_seconds > 300 THEN
        RAISE EXCEPTION 'Invalid TTL: % out of bounds', p_ttl_seconds USING ERRCODE = '22023';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM secure_vault.officer_signing_keys
        WHERE officer_id = p_officer_id 
          AND revoked_at IS NULL
          AND expires_at > pg_catalog.clock_timestamp()
    ) INTO v_key_valid;

    IF NOT v_key_valid THEN
        RAISE EXCEPTION 'Authentication Error: Officer % does not have active signing key', p_officer_id
            USING ERRCODE = '42501';
    END IF;

    p_nonce_id := pg_catalog.gen_random_uuid();
    p_expires_at := pg_catalog.clock_timestamp() + (p_ttl_seconds || ' seconds')::INTERVAL;

    INSERT INTO secure_vault.action_nonces (
        nonce_id, action, target_id, officer_id, expires_at, created_at
    ) VALUES (
        p_nonce_id, p_action, p_target_id, p_officer_id, p_expires_at, pg_catalog.clock_timestamp()
    );
END;
$$;
"""

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

PRIVILEGE_MANAGEMENT_SQL = """
-- 1. Alter Ownership to sec_admin
ALTER FUNCTION public.fn_enforce_transfer_worm_immutability() OWNER TO sec_admin;
ALTER PROCEDURE secure_vault.sp_issue_compliance_nonce(TEXT, UUID, UUID, INTEGER, UUID, TIMESTAMPTZ) OWNER TO sec_admin;
ALTER PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) OWNER TO sec_admin;
ALTER TABLE secure_vault.officer_signing_keys OWNER TO sec_admin;
ALTER TABLE secure_vault.action_nonces OWNER TO sec_admin;
ALTER TABLE secure_vault.redaction_execution_fence OWNER TO sec_admin;
ALTER SCHEMA secure_vault OWNER TO sec_admin;

-- 1b. Schema CREATE Revocation (CR-B3-68)
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 2. Schema USAGE Grants
GRANT USAGE ON SCHEMA secure_vault TO sec_admin, raguard_auth_worker, raguard_compliance;
REVOKE ALL ON SCHEMA secure_vault FROM PUBLIC, raguard_app;

-- 3. Procedure Grants & Revocations
GRANT EXECUTE ON PROCEDURE secure_vault.sp_issue_compliance_nonce(TEXT, UUID, UUID, INTEGER, UUID, TIMESTAMPTZ) TO raguard_auth_worker;
REVOKE EXECUTE ON PROCEDURE secure_vault.sp_issue_compliance_nonce(TEXT, UUID, UUID, INTEGER, UUID, TIMESTAMPTZ) FROM PUBLIC, raguard_app, raguard_compliance;

GRANT EXECUTE ON PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) TO raguard_compliance;
REVOKE EXECUTE ON PROCEDURE secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID) FROM PUBLIC, raguard_app, raguard_auth_worker;

-- 4. Table-Level Grants & Revocations on secure_vault
REVOKE ALL ON ALL TABLES IN SCHEMA secure_vault FROM PUBLIC, raguard_app, raguard_auth_worker, raguard_compliance;
GRANT SELECT, INSERT, UPDATE ON TABLE secure_vault.officer_signing_keys TO sec_admin;
GRANT SELECT, INSERT, UPDATE ON TABLE secure_vault.action_nonces TO sec_admin;
GRANT SELECT, INSERT, DELETE ON TABLE secure_vault.redaction_execution_fence TO sec_admin;

-- 5. Strict Column Privileges on public.workspace_ownership_transfers
REVOKE ALL ON TABLE public.workspace_ownership_transfers FROM PUBLIC, sec_admin, raguard_auth_worker, raguard_compliance;
REVOKE UPDATE ON public.workspace_ownership_transfers FROM raguard_app;

GRANT SELECT ON public.workspace_ownership_transfers TO sec_admin, raguard_app;
GRANT UPDATE (current_owner_email_snapshot, nominated_user_email_snapshot, response_notes, decision_notes)
    ON public.workspace_ownership_transfers TO sec_admin;

GRANT UPDATE (
    status, rejection_reason, responded_at, cancelled_at, expired_at,
    former_owner_choice, former_owner_choice_at, decision_status, decision_deadline_at,
    decided_at, decided_by_user_id, response_notes, decision_notes
) ON public.workspace_ownership_transfers TO raguard_app;

-- 5b. Departure History Table Privileges (CR-B3-75)
REVOKE ALL ON TABLE public.workspace_former_owner_departures FROM PUBLIC;
GRANT SELECT, INSERT ON public.workspace_former_owner_departures TO raguard_app, sec_admin;
REVOKE UPDATE, DELETE ON public.workspace_former_owner_departures FROM PUBLIC, raguard_app, sec_admin, raguard_auth_worker, raguard_compliance;

-- 6. Trigger Function Privileges
ALTER FUNCTION public.fn_enforce_former_owner_departure_worm() OWNER TO sec_admin;
REVOKE ALL ON FUNCTION public.fn_enforce_former_owner_departure_worm() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_enforce_former_owner_departure_worm() TO raguard_app, sec_admin;
REVOKE ALL ON FUNCTION public.fn_enforce_transfer_worm_immutability() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_enforce_transfer_worm_immutability() TO raguard_app, raguard_compliance, sec_admin;

-- 7. Audit Log Privileges
GRANT INSERT, SELECT (id, action, tenant_id, user_id, resource_type, resource_id, details, status, created_at)
    ON public.audit_logs TO sec_admin;
"""


def upgrade():
    # Phase 1: Pre-Flight Assertions
    op.execute(PREFLIGHT_ASSERTION_SQL)

    # Phase 2: Schema Creation
    op.execute("CREATE SCHEMA IF NOT EXISTS secure_vault;")

    # Phase 3: Create Tables in secure_vault
    op.create_table(
        "officer_signing_keys",
        sa.Column("officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("public_key", postgresql.BYTEA(), nullable=False),
        sa.Column("key_algorithm", sa.String(32), server_default="ED25519", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("pg_catalog.clock_timestamp()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("pg_catalog.octet_length(public_key) = 32", name="chk_pubkey_len"),
        sa.CheckConstraint("expires_at > created_at", name="chk_key_expiry"),
        schema="secure_vault",
    )

    op.create_table(
        "action_nonces",
        sa.Column("nonce_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("secure_vault.officer_signing_keys.officer_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_txid", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("pg_catalog.clock_timestamp()"), nullable=False),
        sa.CheckConstraint("action = 'COMPLIANCE_REDACTION'", name="chk_nonce_action"),
        sa.CheckConstraint("expires_at > created_at", name="chk_nonce_expiry"),
        schema="secure_vault",
    )
    op.create_index("ix_action_nonces_lookup", "action_nonces", ["action", "target_id", "consumed_at"], schema="secure_vault")

    op.create_table(
        "redaction_execution_fence",
        sa.Column("txid", sa.BigInteger(), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.workspace_ownership_transfers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nonce_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("secure_vault.action_nonces.nonce_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("secure_vault.officer_signing_keys.officer_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("pg_catalog.clock_timestamp()"), nullable=False),
        sa.PrimaryKeyConstraint("txid", "transfer_id", name="pk_redaction_execution_fence"),
        sa.UniqueConstraint("nonce_id", name="uq_redaction_execution_fence_nonce"),
        sa.CheckConstraint("action = 'COMPLIANCE_REDACTION'", name="chk_fence_action"),
        schema="secure_vault",
    )

    # Phase 4: Create public.workspace_former_owner_departures (WP 7.10)
    op.create_table(
        "workspace_former_owner_departures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("pg_catalog.gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("former_owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.workspace_ownership_transfers.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("departure_type", sa.String(32), nullable=False),
        sa.Column("former_role", sa.String(32), server_default="OWNER", nullable=False),
        sa.Column("retained_role", sa.String(32), nullable=True),
        sa.Column("departure_confirmed_at", sa.DateTime(timezone=True), server_default=sa.text("pg_catalog.clock_timestamp()"), nullable=False),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("departure_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("pg_catalog.clock_timestamp()"), nullable=False),
        sa.CheckConstraint("departure_type IN ('VOLUNTARY_LEAVE', 'NEW_OWNER_REMOVED', 'NEW_OWNER_RETAINED', 'TIMEOUT_AUTO_REMOVED')", name="chk_departure_type"),
        sa.CheckConstraint("(departure_type = 'NEW_OWNER_RETAINED' AND retained_role IN ('ADMIN', 'MEMBER')) OR (departure_type <> 'NEW_OWNER_RETAINED' AND retained_role IS NULL)", name="chk_retained_role_consistency"),
    )
    op.create_index("ix_former_owner_departures_ws", "workspace_former_owner_departures", ["workspace_id", "departure_confirmed_at"])
    op.create_index("ix_former_owner_departures_user", "workspace_former_owner_departures", ["former_owner_id"])

    # Phase 5: Add PII Snapshot Columns to workspace_ownership_transfers (WP 7.12)
    op.add_column("workspace_ownership_transfers", sa.Column("current_owner_email_snapshot", sa.String(255), nullable=True))
    op.add_column("workspace_ownership_transfers", sa.Column("nominated_user_email_snapshot", sa.String(255), nullable=True))

    # Phase 6: Backfill Email Snapshots for Existing Records
    op.execute("""
        UPDATE public.workspace_ownership_transfers t
        SET
            current_owner_email_snapshot = COALESCE(u_owner.email, 'unknown_owner@domain.local'),
            nominated_user_email_snapshot = COALESCE(u_nominee.email, 'unknown_nominee@domain.local')
        FROM public.users u_owner, public.users u_nominee
        WHERE t.nominated_by_user_id = u_owner.id
          AND t.nominee_user_id = u_nominee.id
          AND (t.current_owner_email_snapshot IS NULL OR t.nominated_user_email_snapshot IS NULL);
    """)

    # Enforce NOT NULL on snapshot columns
    op.alter_column("workspace_ownership_transfers", "current_owner_email_snapshot", nullable=False)
    op.alter_column("workspace_ownership_transfers", "nominated_user_email_snapshot", nullable=False)

    # Phase 7: Install WORM Immutability Trigger Functions & Triggers (CR-B3-74)
    op.execute(FUNCTION_SQL_FN_ENFORCE_DEPARTURE_WORM)
    op.execute("DROP TRIGGER IF EXISTS tr_enforce_former_owner_departure_worm ON public.workspace_former_owner_departures;")
    op.execute("""
        CREATE TRIGGER tr_enforce_former_owner_departure_worm
            BEFORE UPDATE OR DELETE ON public.workspace_former_owner_departures
            FOR EACH ROW
            EXECUTE FUNCTION public.fn_enforce_former_owner_departure_worm();
    """)
    op.execute(FUNCTION_SQL_FN_ENFORCE_TRANSFER_WORM)
    op.execute("DROP TRIGGER IF EXISTS tr_enforce_transfer_worm_immutability ON public.workspace_ownership_transfers;")
    op.execute("""
        CREATE TRIGGER tr_enforce_transfer_worm_immutability
            BEFORE UPDATE OR DELETE ON public.workspace_ownership_transfers
            FOR EACH ROW
            EXECUTE FUNCTION public.fn_enforce_transfer_worm_immutability();
    """)

    # Phase 8: Install Stored Procedures
    op.execute(PROCEDURE_SQL_ISSUE_COMPLIANCE_NONCE)
    op.execute(PROCEDURE_SQL_COMPLIANCE_REDACTION)

    # Phase 9: Apply Strict Privilege Management
    for statement in [s.strip() for s in PRIVILEGE_MANAGEMENT_SQL.split(";") if s.strip()]:
        op.execute(statement + ";")


def downgrade():
    # Downgrade Guard: Abort if departure history records or redacted transfers exist (CR-B3-16, CR-B3-23)
    op.execute("""
        DO $$
        DECLARE
            v_dep_count INT;
            v_redacted_count INT;
        BEGIN
            SELECT count(*) INTO v_dep_count FROM public.workspace_former_owner_departures;
            IF v_dep_count > 0 THEN
                RAISE EXCEPTION 'Downgrade Aborted: % departure history records exist. Downgrade violates audit durability', v_dep_count
                    USING ERRCODE = '55000';
            END IF;

            SELECT count(*) INTO v_redacted_count FROM public.workspace_ownership_transfers
            WHERE current_owner_email_snapshot = '[REDACTED_PII]' 
               OR nominated_user_email_snapshot = '[REDACTED_PII]'
               OR response_notes = '[REDACTED_PII]'
               OR decision_notes = '[REDACTED_PII]';
            IF v_redacted_count > 0 THEN
                RAISE EXCEPTION 'Downgrade Aborted: % compliance-redacted transfers exist. Downgrade violates legal retention', v_redacted_count
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)

    # Remove Triggers and Procedures
    op.execute("DROP TRIGGER IF EXISTS tr_enforce_former_owner_departure_worm ON public.workspace_former_owner_departures;")
    op.execute("DROP FUNCTION IF EXISTS public.fn_enforce_former_owner_departure_worm();")
    op.execute("DROP TRIGGER IF EXISTS tr_enforce_transfer_worm_immutability ON public.workspace_ownership_transfers;")
    op.execute("DROP FUNCTION IF EXISTS public.fn_enforce_transfer_worm_immutability();")
    op.execute("DROP PROCEDURE IF EXISTS secure_vault.sp_execute_compliance_redaction(BYTEA, BYTEA, UUID);")
    op.execute("DROP PROCEDURE IF EXISTS secure_vault.sp_issue_compliance_nonce(TEXT, UUID, UUID, INTEGER, UUID, TIMESTAMPTZ);")

    # Drop Tables
    op.drop_table("workspace_former_owner_departures")
    op.drop_table("redaction_execution_fence", schema="secure_vault")
    op.drop_table("action_nonces", schema="secure_vault")
    op.drop_table("officer_signing_keys", schema="secure_vault")

    # Remove Columns
    op.drop_column("workspace_ownership_transfers", "nominated_user_email_snapshot")
    op.drop_column("workspace_ownership_transfers", "current_owner_email_snapshot")

    # Drop Schema
    op.execute("DROP SCHEMA IF EXISTS secure_vault CASCADE;")
