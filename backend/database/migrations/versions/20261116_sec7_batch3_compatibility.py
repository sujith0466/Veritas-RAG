"""section 7 batch 3 corrective compatibility migration

Revision ID: 20261116_sec7_batch3_compatibility
Revises: 20261116_sec7_batch3_remediation
Create Date: 2026-11-16 10:25:00.000000

VRAG-AUTH-SEC7-BATCH3-STAGE-H-20261116-01:
- F-B3-TRIGGER-01 through F-B3-TRIGGER-05: Reconcile canonical 11-transition lifecycle engine
- F-B3-TRIGGER-06: NULL-safe allowlist validation using IS DISTINCT FROM '[REDACTED_PII]'
- Fail-closed downgrade durability guard against incompatible canonical states
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261116_sec7_batch3_compatibility"
down_revision = "20261116_sec7_batch3_remediation"
branch_labels = None
depends_on = None

FUNCTION_SQL_FN_ENFORCE_TRANSFER_WORM_COMPATIBILITY = r"""
CREATE OR REPLACE FUNCTION public.fn_enforce_transfer_worm_immutability()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $function$
DECLARE
    v_fence_nonce_id UUID;
    v_fence_action VARCHAR(64);
    v_fence_officer_id UUID;
BEGIN
    -- =========================================================================
    -- SECTION 1: UNCONDITIONAL PROHIBITION OF DELETE OPERATIONS (PO-D32-03)
    -- =========================================================================
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'WORM Violation: Deletion of workspace ownership transfer records is strictly prohibited under PO-D32-03'
            USING ERRCODE = '55000';
    END IF;

    -- =========================================================================
    -- SECTION 2: CORE TRANSFER IDENTITY INVARIANTS (PERMANENTLY IMMUTABLE)
    -- =========================================================================
    IF NEW.id IS DISTINCT FROM OLD.id OR
       NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR
       NEW.nominated_by_user_id IS DISTINCT FROM OLD.nominated_by_user_id OR
       NEW.nominee_user_id IS DISTINCT FROM OLD.nominee_user_id OR
       NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'WORM Violation: Core transfer identity attributes (id, workspace_id, nominated_by, nominee, created_at) are permanently immutable'
            USING ERRCODE = '55000';
    END IF;

    -- =========================================================================
    -- SECTION 3: COMPLIANCE PERSONAL DATA REDACTION BRANCH (CR-B3-87)
    -- PERIMETER FIREWALL: All mutations to PII fields or marker injection
    -- are evaluated here first. Unauthorized callers fail with SQLSTATE 42501.
    -- =========================================================================
    IF (NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot) OR
       (NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot) OR
       (NEW.response_notes = '[REDACTED_PII]' AND OLD.response_notes IS DISTINCT FROM NEW.response_notes) OR
       (NEW.decision_notes = '[REDACTED_PII]' AND OLD.decision_notes IS DISTINCT FROM NEW.decision_notes) THEN

        -- 3.1 Strict Security Role Check (Fail-Closed Perimeter)
        IF CURRENT_USER <> 'sec_admin' THEN
            RAISE EXCEPTION 'Authorization Violation: Compliance redaction requires sec_admin role context, received "%"', CURRENT_USER
                USING ERRCODE = '42501';
        END IF;

        -- 3.2 Atomic Consumption of Transaction Execution Fence
        DELETE FROM secure_vault.redaction_execution_fence
        WHERE txid = pg_catalog.txid_current() 
          AND transfer_id = NEW.id
        RETURNING nonce_id, action, officer_id INTO v_fence_nonce_id, v_fence_action, v_fence_officer_id;

        IF v_fence_nonce_id IS NULL THEN
            RAISE EXCEPTION 'Authorization Violation: Missing or previously consumed execution fence for transfer % in txid %', NEW.id, pg_catalog.txid_current()
                USING ERRCODE = '42501';
        END IF;

        IF v_fence_action <> 'COMPLIANCE_REDACTION' THEN
            RAISE EXCEPTION 'Authorization Violation: Execution fence action "%" does not match required "COMPLIANCE_REDACTION"', v_fence_action
                USING ERRCODE = '42501';
        END IF;

        -- 3.3 Verify Nonce Binding in secure_vault.action_nonces
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

        -- 3.4 Strict Allowlist and Single-Redaction Checks on PII Columns
        -- HARDENED (F-B3-TRIGGER-06): NULL-safe "IS DISTINCT FROM '[REDACTED_PII]'"
        IF NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot THEN
            IF OLD.current_owner_email_snapshot = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: current_owner_email_snapshot is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.current_owner_email_snapshot IS DISTINCT FROM '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: current_owner_email_snapshot can only be mutated to "[REDACTED_PII]", received "%"', NEW.current_owner_email_snapshot
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        IF NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            IF OLD.nominated_user_email_snapshot = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: nominated_user_email_snapshot is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.nominated_user_email_snapshot IS DISTINCT FROM '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: nominated_user_email_snapshot can only be mutated to "[REDACTED_PII]", received "%"', NEW.nominated_user_email_snapshot
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            IF OLD.response_notes = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.response_notes IS NULL THEN
                RAISE EXCEPTION 'Redaction Precondition Error: Cannot redact response_notes when field is NULL'
                    USING ERRCODE = '22023';
            END IF;
            IF NEW.response_notes IS DISTINCT FROM '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: response_notes can only be redacted to "[REDACTED_PII]", received "%"', NEW.response_notes
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            IF OLD.decision_notes = '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.decision_notes IS NULL THEN
                RAISE EXCEPTION 'Redaction Precondition Error: Cannot redact decision_notes when field is NULL'
                    USING ERRCODE = '22023';
            END IF;
            IF NEW.decision_notes IS DISTINCT FROM '[REDACTED_PII]' THEN
                RAISE EXCEPTION 'Redaction Allowlist Violation: decision_notes can only be redacted to "[REDACTED_PII]", received "%"', NEW.decision_notes
                    USING ERRCODE = '22023';
            END IF;
        END IF;

        -- 3.5 Absolute Invariance of All 17 Non-PII Fields Under Redaction
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

    -- =========================================================================
    -- SECTION 4: CANONICAL 11-TRANSITION FORWARD LIFECYCLE ENGINE
    -- Unchanged [REDACTED_PII] values evaluate IS DISTINCT FROM to FALSE,
    -- allowing lifecycle progression. Any mutation to notes raises 55000.
    -- =========================================================================

    -- Transition 1: PENDING -> CANCELLED
    IF OLD.status = 'PENDING' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'CANCELLED' THEN
        IF NEW.cancelled_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: CANCELLED status requires non-null cancelled_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.cancelled_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: cancelled_at is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS NOT NULL OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_status IS DISTINCT FROM OLD.decision_status OR NEW.decision_deadline_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during CANCELLED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 2: PENDING -> REJECTED
    IF OLD.status = 'PENDING' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'REJECTED' THEN
        IF NEW.responded_at IS NULL OR NEW.rejection_reason IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: REJECTED status requires non-null responded_at and rejection_reason'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.responded_at IS NOT NULL OR OLD.rejection_reason IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: responded_at and rejection_reason are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason = '[REDACTED_PII]' THEN
            RAISE EXCEPTION 'Redaction Violation: "[REDACTED_PII]" is reserved for compliance redaction'
                USING ERRCODE = '22023';
        END IF;
        -- Single-Assignment and Redaction Durability for response_notes
        IF (OLD.response_notes IS NOT NULL AND NEW.response_notes IS DISTINCT FROM OLD.response_notes) THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.response_notes = '[REDACTED_PII]' AND NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.cancelled_at IS NOT NULL OR
           NEW.expired_at IS NOT NULL OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS NOT NULL OR NEW.decision_status IS DISTINCT FROM OLD.decision_status OR
           NEW.decision_deadline_at IS NOT NULL OR NEW.decided_at IS NOT NULL OR
           NEW.decided_by_user_id IS NOT NULL OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during REJECTED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 3: PENDING -> EXPIRED
    IF OLD.status = 'PENDING' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'EXPIRED' THEN
        IF NEW.expired_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: EXPIRED status requires non-null expired_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.expired_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: expired_at is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.responded_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL OR
           NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_status IS DISTINCT FROM OLD.decision_status OR NEW.decision_deadline_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.response_notes IS DISTINCT FROM OLD.response_notes OR NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during EXPIRED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 4: PENDING -> ACCEPTED (decision_status remains PENDING)
    IF OLD.status = 'PENDING' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.decision_status = 'PENDING' THEN
        IF NEW.responded_at IS NULL OR NEW.decision_deadline_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: ACCEPTED requires non-null responded_at and decision_deadline_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.responded_at IS NOT NULL OR OLD.decision_deadline_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: responded_at and decision_deadline_at are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Single-Assignment and Redaction Durability for response_notes
        IF (OLD.response_notes IS NOT NULL AND NEW.response_notes IS DISTINCT FROM OLD.response_notes) THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.response_notes = '[REDACTED_PII]' AND NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Violation: response_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes OR
           NEW.rejection_reason IS NOT NULL OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR
           NEW.cancelled_at IS NOT NULL OR NEW.expired_at IS NOT NULL OR
           NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during ACCEPTED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 5: ACCEPTED & choice=PENDING -> choice=STAY (dec_status remains PENDING)
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'STAY' AND NEW.decision_status = 'PENDING' THEN
        IF NEW.former_owner_choice_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: STAY choice requires non-null former_owner_choice_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.former_owner_choice_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: former_owner_choice_at is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Invariance of decision_notes and response_notes
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during STAY choice transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during STAY choice transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.decision_status IS DISTINCT FROM OLD.decision_status OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.decided_at IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during STAY choice transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 6: ACCEPTED & choice=PENDING -> choice=LEAVE & dec_status=DECIDED_REMOVED
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'LEAVE' AND NEW.decision_status = 'DECIDED_REMOVED' THEN
        IF NEW.former_owner_choice_at IS NULL OR NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: LEAVE choice requires non-null former_owner_choice_at, decided_at, and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.former_owner_choice_at IS NOT NULL OR OLD.decided_at IS NOT NULL OR OLD.decided_by_user_id IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: former_owner_choice_at, decided_at, and decided_by_user_id are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Invariance of decision_notes and response_notes
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during LEAVE choice transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during LEAVE choice transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during LEAVE choice transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 7: ACCEPTED & choice=STAY & dec_status=PENDING -> dec_status=DECIDED_ADMIN
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'STAY' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'STAY' AND NEW.decision_status = 'DECIDED_ADMIN' THEN
        IF NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECIDED_ADMIN requires non-null decided_at and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.decided_at IS NOT NULL OR OLD.decided_by_user_id IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: decided_at and decided_by_user_id are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Single-Assignment and Redaction Durability for decision_notes
        IF (OLD.decision_notes IS NOT NULL AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes) THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.decision_notes = '[REDACTED_PII]' AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.rejection_reason IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECIDED_ADMIN transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 8: ACCEPTED & choice=STAY & dec_status=PENDING -> dec_status=DECIDED_MEMBER
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'STAY' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'STAY' AND NEW.decision_status = 'DECIDED_MEMBER' THEN
        IF NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECIDED_MEMBER requires non-null decided_at and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.decided_at IS NOT NULL OR OLD.decided_by_user_id IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: decided_at and decided_by_user_id are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Single-Assignment and Redaction Durability for decision_notes
        IF (OLD.decision_notes IS NOT NULL AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes) THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.decision_notes = '[REDACTED_PII]' AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.rejection_reason IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECIDED_MEMBER transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 9: ACCEPTED & choice=STAY & dec_status=PENDING -> dec_status=DECIDED_REMOVED
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'STAY' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'STAY' AND NEW.decision_status = 'DECIDED_REMOVED' THEN
        IF NEW.decided_at IS NULL OR NEW.decided_by_user_id IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: DECIDED_REMOVED requires non-null decided_at and decided_by_user_id'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.decided_at IS NOT NULL OR OLD.decided_by_user_id IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: decided_at and decided_by_user_id are single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Single-Assignment and Redaction Durability for decision_notes
        IF (OLD.decision_notes IS NOT NULL AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes) THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        IF OLD.decision_notes = '[REDACTED_PII]' AND NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Violation: decision_notes is already redacted and permanently immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes OR
           NEW.rejection_reason IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during DECIDED_REMOVED transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 10: ACCEPTED & choice=STAY & dec_status=PENDING -> dec_status=FALLBACK_ADMIN
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'STAY' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'STAY' AND NEW.decision_status = 'FALLBACK_ADMIN' THEN
        IF NEW.decided_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: FALLBACK_ADMIN requires non-null decided_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.decided_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: decided_at is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Invariance of decision_notes and response_notes
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during FALLBACK_ADMIN transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during FALLBACK_ADMIN transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS DISTINCT FROM OLD.former_owner_choice_at OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during FALLBACK_ADMIN transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- Transition 11: ACCEPTED & choice=PENDING & dec_status=PENDING -> dec_status=TIMED_OUT
    IF OLD.status = 'ACCEPTED' AND OLD.former_owner_choice = 'PENDING' AND OLD.decision_status = 'PENDING' AND NEW.status = 'ACCEPTED' AND NEW.former_owner_choice = 'PENDING' AND NEW.decision_status = 'TIMED_OUT' THEN
        IF NEW.decided_at IS NULL THEN
            RAISE EXCEPTION 'Lifecycle Precondition Error: TIMED_OUT requires non-null decided_at'
                USING ERRCODE = '22023';
        END IF;
        IF OLD.decided_at IS NOT NULL THEN
            RAISE EXCEPTION 'WORM Violation: decided_at is single-assignment and cannot be overwritten'
                USING ERRCODE = '55000';
        END IF;
        -- Invariance of decision_notes and response_notes
        IF NEW.decision_notes IS DISTINCT FROM OLD.decision_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during TIMED_OUT transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.response_notes IS DISTINCT FROM OLD.response_notes THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during TIMED_OUT transition'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.rejection_reason IS NOT NULL OR NEW.decided_by_user_id IS NOT NULL OR
           NEW.status IS DISTINCT FROM OLD.status OR NEW.former_owner_choice IS DISTINCT FROM OLD.former_owner_choice OR
           NEW.former_owner_choice_at IS NOT NULL OR
           NEW.decision_deadline_at IS DISTINCT FROM OLD.decision_deadline_at OR
           NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.responded_at IS DISTINCT FROM OLD.responded_at OR
           NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR NEW.expired_at IS DISTINCT FROM OLD.expired_at OR
           NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot OR
           NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot THEN
            RAISE EXCEPTION 'WORM Transition Violation: Unauthorized column mutation during TIMED_OUT transition'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    -- =========================================================================
    -- SECTION 5: DEFAULT FAIL-CLOSED UNCONDITIONAL REJECTION (PO-D32-03)
    -- =========================================================================
    RAISE EXCEPTION 'WORM Violation: Mutation from status=%, choice=%, dec_status=% to status=%, choice=%, dec_status=% is strictly prohibited under PO-D32-03',
        OLD.status, OLD.former_owner_choice, OLD.decision_status, NEW.status, NEW.former_owner_choice, NEW.decision_status
        USING ERRCODE = '55000';
END;
$function$;
"""

FUNCTION_SQL_PRE_CORRECTIVE_REMEDIATION = r"""
CREATE OR REPLACE FUNCTION public.fn_enforce_transfer_worm_immutability()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $function$
DECLARE
    v_fence_nonce_id UUID;
    v_fence_action VARCHAR(64);
    v_fence_officer_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'WORM Violation: Deletion of workspace ownership transfer records is strictly prohibited under PO-D32-03'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id OR
       NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR
       NEW.nominated_by_user_id IS DISTINCT FROM OLD.nominated_by_user_id OR
       NEW.nominee_user_id IS DISTINCT FROM OLD.nominee_user_id OR
       NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'WORM Violation: Core transfer identity attributes (id, workspace_id, nominated_by, nominee, created_at) are permanently immutable'
            USING ERRCODE = '55000';
    END IF;

    IF (NEW.current_owner_email_snapshot IS DISTINCT FROM OLD.current_owner_email_snapshot) OR
       (NEW.nominated_user_email_snapshot IS DISTINCT FROM OLD.nominated_user_email_snapshot) OR
       (NEW.response_notes = '[REDACTED_PII]' AND OLD.response_notes IS DISTINCT FROM NEW.response_notes) OR
       (NEW.decision_notes = '[REDACTED_PII]' AND OLD.decision_notes IS DISTINCT FROM NEW.decision_notes) THEN

        IF CURRENT_USER <> 'sec_admin' THEN
            RAISE EXCEPTION 'Authorization Violation: Compliance redaction requires sec_admin role context, received "%"', CURRENT_USER
                USING ERRCODE = '42501';
        END IF;

        DELETE FROM secure_vault.redaction_execution_fence
        WHERE txid = pg_catalog.txid_current() 
          AND transfer_id = NEW.id
        RETURNING nonce_id, action, officer_id INTO v_fence_nonce_id, v_fence_action, v_fence_officer_id;

        IF v_fence_nonce_id IS NULL THEN
            RAISE EXCEPTION 'Authorization Violation: Missing or previously consumed execution fence for transfer % in txid %', NEW.id, pg_catalog.txid_current()
                USING ERRCODE = '42501';
        END IF;

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

    RAISE EXCEPTION 'WORM Violation: Unrecognized transition under pre-corrective definition'
        USING ERRCODE = '55000';
END;
$function$;
"""


def upgrade():
    # 1. Apply Corrected, NULL-safe PL/pgSQL Function Definition
    op.execute(FUNCTION_SQL_FN_ENFORCE_TRANSFER_WORM_COMPATIBILITY)

    # 2. Re-affirm sec_admin ownership and execution permissions
    op.execute("ALTER FUNCTION public.fn_enforce_transfer_worm_immutability() OWNER TO sec_admin;")
    op.execute("REVOKE ALL ON FUNCTION public.fn_enforce_transfer_worm_immutability() FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.fn_enforce_transfer_worm_immutability() TO raguard_app, sec_admin;")


def downgrade():
    # 1. Fail-Closed Durability Guard for Canonical Lifecycle States
    op.execute("""
        DO $$
        DECLARE
            v_incompatible_count INT;
            v_summary TEXT;
        BEGIN
            SELECT count(*),
                   string_agg(DISTINCT format('(status=%s, choice=%s, dec=%s)', status, former_owner_choice, decision_status), '; ')
            INTO v_incompatible_count, v_summary
            FROM public.workspace_ownership_transfers
            WHERE former_owner_choice IN ('STAY', 'LEAVE')
               OR decision_status IN ('DECIDED_ADMIN', 'DECIDED_MEMBER', 'DECIDED_REMOVED', 'FALLBACK_ADMIN', 'TIMED_OUT')
               OR status IN ('REJECTED', 'ACCEPTED');

            IF v_incompatible_count > 0 THEN
                RAISE EXCEPTION 'Downgrade Aborted: % transfer records exist in states incompatible with pre-corrective trigger (Found: %). Restoring pre-corrective trigger would permanently invalidate lifecycle progression under PO-D32-03',
                    v_incompatible_count, v_summary
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)

    # 2. Restore Pre-Corrective Trigger Function Definition
    op.execute(FUNCTION_SQL_PRE_CORRECTIVE_REMEDIATION)
    op.execute("ALTER FUNCTION public.fn_enforce_transfer_worm_immutability() OWNER TO sec_admin;")
    op.execute("REVOKE ALL ON FUNCTION public.fn_enforce_transfer_worm_immutability() FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.fn_enforce_transfer_worm_immutability() TO raguard_app, sec_admin;")
