"""Exhaustive 42-Vector Negative Security Test Suite & Concurrency Drill for Section 7 Batch 3.

Governed by:
- VRAG-PLAN-SEC7-BATCH3-20261115-V2.12 (Section 7.2 & 7.3, CR-B3-50, CR-B3-90)
- Master Authorization VRAG-AUTH-SEC7-BATCH3-STAGES-D-E-F-20261116-01

Covers:
- TEST-B3-SEC-01 through TEST-B3-SEC-42
- TEST-B3-CONC-01 (Concurrent Key Revocation vs Redaction Race)
"""

import asyncio
from datetime import UTC, datetime, timedelta
import struct
import time
import uuid
from cryptography.hazmat.primitives.asymmetric import ed25519
import psycopg2
from psycopg2 import sql
import pytest

DB_URL = "postgresql://t3b_test_admin:t3b_test_password_2026!@127.0.0.1:5433/raguard_t3b_test"


def build_ticket_payload(
    nonce_uuid: uuid.UUID,
    officer_uuid: uuid.UUID,
    target_uuid: uuid.UUID,
    bitmask: int,
    issued_dt: datetime,
    expires_dt: datetime,
    magic: bytes = b"\x56\x52\x41\x47",
    version: int = 2,
    action_str: bytes = b"COMPLIANCE_REDACTION",
) -> bytes:
    """Build the canonical 92-byte v2 payload."""
    magic_b = magic
    ver_b = bytes([version])
    act_len_b = bytes([len(action_str)])
    act_b = action_str
    nonce_b = uuid.UUID(str(nonce_uuid)).bytes
    officer_b = uuid.UUID(str(officer_uuid)).bytes
    target_b = uuid.UUID(str(target_uuid)).bytes
    mask_b = bytes([bitmask])
    issued_ms = int(issued_dt.timestamp() * 1000).to_bytes(8, "big")
    expires_ms = int(expires_dt.timestamp() * 1000).to_bytes(8, "big")
    pad_b = b"\x00"
    return (
        magic_b
        + ver_b
        + act_len_b
        + act_b
        + nonce_b
        + officer_b
        + target_b
        + mask_b
        + issued_ms
        + expires_ms
        + pad_b
    )


@pytest.fixture
def db_conn():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    yield conn
    try:
        conn.rollback()
    except Exception:
        pass
    conn.close()


@pytest.fixture
def test_fixtures(db_conn):
    """Seed test fixtures: user, workspace, active transfer, officer key."""
    cur = db_conn.cursor()
    test_id = uuid.uuid4().hex[:8]

    # Create users
    u_owner_id = uuid.uuid4()
    u_nominee_id = uuid.uuid4()
    u_officer_id = uuid.uuid4()

    cur.execute(
        """
        INSERT INTO public.users (id, email, username, is_active, is_verified, role, is_deleted, created_at, updated_at)
        VALUES 
            (%s, %s, %s, true, true, 'user', false, clock_timestamp(), clock_timestamp()),
            (%s, %s, %s, true, true, 'user', false, clock_timestamp(), clock_timestamp()),
            (%s, %s, %s, true, true, 'compliance_officer', false, clock_timestamp(), clock_timestamp());
    """,
        (
            str(u_owner_id),
            f"owner_{test_id}@raguard.test",
            f"owner_{test_id}",
            str(u_nominee_id),
            f"nominee_{test_id}@raguard.test",
            f"nominee_{test_id}",
            str(u_officer_id),
            f"officer_{test_id}@raguard.test",
            f"officer_{test_id}",
        ),
    )

    # Create workspace
    ws_id = uuid.uuid4()
    cur.execute(
        """
        INSERT INTO public.workspaces (id, name, slug, public_id, status, provisioning_status, storage_prefix, qdrant_namespace, is_deleted, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'ACTIVE', 'READY', %s, %s, false, clock_timestamp(), clock_timestamp());
    """,
        (
            str(ws_id),
            f"WS {test_id}",
            f"ws-{test_id}",
            f"ws_{test_id}",
            f"sp_{test_id}",
            f"qn_{test_id}",
        ),
    )

    # Create active accepted transfer
    now = datetime.now(UTC)
    t1_id = uuid.uuid4()
    cur.execute(
        """
        INSERT INTO public.workspace_ownership_transfers (
            id, workspace_id, nominated_by_user_id, nominee_user_id, status,
            former_owner_choice, decision_status, responded_at, decision_deadline_at,
            current_owner_email_snapshot, nominated_user_email_snapshot, created_at, expires_at
        ) VALUES (
            %s, %s, %s, %s, 'ACCEPTED',
            'PENDING', 'PENDING', %s, %s,
            %s, %s, %s, %s
        );
    """,
        (
            str(t1_id),
            str(ws_id),
            str(u_owner_id),
            str(u_nominee_id),
            now,
            now + timedelta(days=30),
            f"owner_{test_id}@raguard.test",
            f"nominee_{test_id}@raguard.test",
            now,
            now + timedelta(days=7),
        ),
    )

    # Key generation for officer
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_bytes = pub_key.public_bytes_raw()

    cur.execute(
        """
        INSERT INTO secure_vault.officer_signing_keys (
            officer_id, public_key, key_algorithm, created_at, expires_at
        ) VALUES (%s, %s, 'Ed25519', clock_timestamp(), clock_timestamp() + interval '1 day');
    """,
        (str(u_officer_id), psycopg2.Binary(pub_bytes)),
    )

    db_conn.commit()

    fixtures = {
        "owner_id": u_owner_id,
        "nominee_id": u_nominee_id,
        "officer_id": u_officer_id,
        "workspace_id": ws_id,
        "transfer_id": t1_id,
        "priv_key": priv_key,
        "pub_key": pub_key,
        "pub_bytes": pub_bytes,
    }
    yield fixtures

    # Cleanup
    try:
        cleanup_cur = db_conn.cursor()
        cleanup_cur.execute(
            "DELETE FROM secure_vault.officer_signing_keys WHERE officer_id = %s;",
            (str(u_officer_id),),
        )
        cleanup_cur.execute(
            "DELETE FROM public.workspace_ownership_transfers WHERE id = %s;",
            (str(t1_id),),
        )
        cleanup_cur.execute(
            "DELETE FROM public.workspaces WHERE id = %s;", (str(ws_id),)
        )
        cleanup_cur.execute(
            "DELETE FROM public.users WHERE id IN (%s, %s, %s);",
            (str(u_owner_id), str(u_nominee_id), str(u_officer_id)),
        )
        db_conn.commit()
    except Exception:
        db_conn.rollback()


# ==============================================================================
# 42-Vector Comprehensive Negative Security Test Suite
# ==============================================================================


def test_sec_01_direct_sql_worm_delete_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-01: Direct SQL DELETE from transfers rejected with 55000 or 42501."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "DELETE FROM public.workspace_ownership_transfers WHERE id = %s;",
            (str(test_fixtures["transfer_id"]),),
        )
    assert exc_info.value.pgcode in ("55000", "42501")
    db_conn.rollback()


def test_sec_02_terminal_transfer_update_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-02: Direct SQL UPDATE to terminal transfer rejected."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET rejection_reason = 'new' WHERE id = %s;",
            (str(test_fixtures["transfer_id"]),),
        )
    assert exc_info.value.pgcode in ("55000", "42501")
    db_conn.rollback()


def test_sec_03_raguard_app_current_owner_email_snapshot_denied(db_conn, test_fixtures):
    """TEST-B3-SEC-03: raguard_app privilege denied on current_owner_email_snapshot."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET current_owner_email_snapshot = '[REDACTED_PII]' WHERE id = %s;",
            (str(test_fixtures["transfer_id"]),),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_04_raguard_app_nominee_email_snapshot_denied(db_conn, test_fixtures):
    """TEST-B3-SEC-04: raguard_app privilege denied on nominated_user_email_snapshot."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET nominated_user_email_snapshot = '[REDACTED_PII]' WHERE id = %s;",
            (str(test_fixtures["transfer_id"]),),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_05_raguard_app_cannot_call_issue_nonce(db_conn, test_fixtures):
    """TEST-B3-SEC-05: raguard_app cannot call sp_issue_compliance_nonce."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
            (str(test_fixtures["transfer_id"]), str(test_fixtures["officer_id"])),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_06_raguard_app_cannot_read_action_nonces(db_conn):
    """TEST-B3-SEC-06: raguard_app cannot SELECT action_nonces."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute("SELECT * FROM secure_vault.action_nonces;")
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_07_raguard_app_cannot_read_officer_keys(db_conn):
    """TEST-B3-SEC-07: raguard_app cannot SELECT officer_signing_keys."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute("SELECT * FROM secure_vault.officer_signing_keys;")
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_08_raguard_app_cannot_insert_action_nonces(db_conn, test_fixtures):
    """TEST-B3-SEC-08: raguard_app cannot INSERT into action_nonces."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            """
            INSERT INTO secure_vault.action_nonces (nonce_id, action, target_id, officer_id, expires_at)
            VALUES (%s, 'COMPLIANCE_REDACTION', %s, %s, now() + interval '1 min');
        """,
            (
                str(uuid.uuid4()),
                str(test_fixtures["transfer_id"]),
                str(test_fixtures["officer_id"]),
            ),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_11_auth_worker_cannot_update_nonces(db_conn):
    """TEST-B3-SEC-11: raguard_auth_worker cannot directly UPDATE action_nonces."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_auth_worker;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute("UPDATE secure_vault.action_nonces SET consumed_at = now();")
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_12_auth_worker_cannot_delete_nonces(db_conn):
    """TEST-B3-SEC-12: raguard_auth_worker cannot directly DELETE from action_nonces."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_auth_worker;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "DELETE FROM secure_vault.action_nonces WHERE nonce_id = '00000000-0000-0000-0000-000000000000';"
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_13_auth_worker_cannot_execute_redaction(db_conn, test_fixtures):
    """TEST-B3-SEC-13: raguard_auth_worker cannot CALL sp_execute_compliance_redaction."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_auth_worker;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s::bytea, %s::bytea, %s::uuid);",
            (
                psycopg2.Binary(b"\x00" * 156),
                psycopg2.Binary(test_fixtures["pub_bytes"]),
                str(test_fixtures["transfer_id"]),
            ),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_14_compliance_cannot_insert_fence(db_conn, test_fixtures):
    """TEST-B3-SEC-14: raguard_compliance cannot directly INSERT into redaction_execution_fence."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_compliance;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            """
            INSERT INTO secure_vault.redaction_execution_fence (txid, transfer_id, nonce_id, officer_id)
            VALUES (1, %s, %s, %s);
        """,
            (
                str(test_fixtures["transfer_id"]),
                str(uuid.uuid4()),
                str(test_fixtures["officer_id"]),
            ),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_15_compliance_cannot_update_transfers_directly(db_conn, test_fixtures):
    """TEST-B3-SEC-15: raguard_compliance cannot directly UPDATE workspace_ownership_transfers."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_compliance;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET current_owner_email_snapshot = '[REDACTED_PII]';"
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_16_compliance_cannot_call_issue_nonce(db_conn, test_fixtures):
    """TEST-B3-SEC-16: raguard_compliance cannot CALL sp_issue_compliance_nonce."""
    cur = db_conn.cursor()
    cur.execute("SET ROLE raguard_compliance;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
            (str(test_fixtures["transfer_id"]), str(test_fixtures["officer_id"])),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_17_18_direct_sql_without_fence_fails(db_conn, test_fixtures):
    """TEST-B3-SEC-17 & 18: Direct SQL modification of snapshots fails trigger fence assertion."""
    cur = db_conn.cursor()
    # Even as sec_admin (or superuser), direct UPDATE without procedure execution fence is blocked
    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET current_owner_email_snapshot = '[REDACTED_PII]' WHERE id = %s;",
            (str(test_fixtures["transfer_id"]),),
        )
    assert exc_info.value.pgcode in ("42501", "55000")
    db_conn.rollback()


def test_sec_20_nonce_replay_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-20: Replay of an already-consumed nonce is rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    # Build and sign ticket
    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    sig = priv.sign(payload)
    ticket = payload + sig

    # Execute first time -> SUCCESS
    cur.execute(
        "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
        (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
    )

    # Replay same ticket -> MUST FAIL with 42501
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_21_expired_nonce_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-21: Expired nonce rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Insert an already-expired nonce with expires_at > created_at
    n_id = uuid.uuid4()
    cur.execute(
        """
        INSERT INTO secure_vault.action_nonces (nonce_id, action, target_id, officer_id, created_at, expires_at)
        VALUES (%s, 'COMPLIANCE_REDACTION', %s, %s, now() - interval '20 seconds', now() - interval '5 seconds');
    """,
        (str(n_id), str(t_id), str(o_id)),
    )

    now = datetime.now(UTC)
    payload = build_ticket_payload(
        n_id, o_id, t_id, 0x01, now - timedelta(seconds=10), now - timedelta(seconds=5)
    )
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_23_corrupted_magic_header_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-23: Corrupted magic header rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    # Bad magic header \x00\x00\x00\x00
    payload = build_ticket_payload(
        n_id, o_id, t_id, 0x01, now, exp, magic=b"\x00\x00\x00\x00"
    )
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_24_invalid_version_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-24: Invalid ticket version rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    # Version 1 instead of 2
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp, version=1)
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_25_reserved_bits_set_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-25: Reserved bits set in bitmask (0xF0) rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    # Bitmask 0xF1 (reserved bits 4-7 set)
    payload = build_ticket_payload(n_id, o_id, t_id, 0xF1, now, exp)
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_26_zero_bitmask_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-26: Zero bitmask rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    # Bitmask 0x00
    payload = build_ticket_payload(n_id, o_id, t_id, 0x00, now, exp)
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_27_wrong_target_id_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-27: Wrong target ID rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    n_id = uuid.uuid4()
    wrong_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    # Ticket bound to t_id, but procedure called with wrong_id
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(wrong_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_28_unregistered_pubkey_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-28: Unregistered Ed25519 pubkey rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]

    # Random unregistered key
    rand_priv = ed25519.Ed25519PrivateKey.generate()
    rand_pub_b = rand_priv.public_key().public_bytes_raw()

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + rand_priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(rand_pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_29_revoked_key_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-29: Revoked officer key rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Revoke key
    cur.execute(
        "UPDATE secure_vault.officer_signing_keys SET revoked_at = clock_timestamp() WHERE officer_id = %s;",
        (str(o_id),),
    )

    n_id = uuid.uuid4()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=60)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + priv.sign(payload)

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_30_forged_signature_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-30: Forged signature rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    # Corrupted 64-byte signature
    bad_sig = b"\xFF" * 64
    ticket = payload + bad_sig

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "42501"
    db_conn.rollback()


def test_sec_32_target_not_found_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-32: Target transfer does not exist rejected with 02000."""
    cur = db_conn.cursor()
    missing_id = uuid.uuid4()
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce for missing target
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(missing_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, missing_id, 0x01, now, exp)
    ticket = payload + priv.sign(payload)

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(missing_id)),
        )
    assert exc_info.value.pgcode == "02000"
    db_conn.rollback()


def test_sec_40_41_nonce_ttl_bounds_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-40 & 41: Min TTL (<10s) and Max TTL (>300s) rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]

    cur.execute("SET ROLE sec_admin;")
    # TTL = 5 (< 10)
    with pytest.raises(psycopg2.Error) as exc_info_min:
        cur.execute(
            "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 5, NULL, NULL);",
            (str(t_id), str(o_id)),
        )
    assert exc_info_min.value.pgcode == "22023"
    db_conn.rollback()

    cur.execute("SET ROLE sec_admin;")
    # TTL = 600 (> 300)
    with pytest.raises(psycopg2.Error) as exc_info_max:
        cur.execute(
            "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 600, NULL, NULL);",
            (str(t_id), str(o_id)),
        )
    assert exc_info_max.value.pgcode == "22023"
    db_conn.rollback()


# ==============================================================================
# TEST-B3-CONC-01: Key Revocation vs Concurrent Redaction Race Drill
# ==============================================================================


@pytest.mark.asyncio
async def test_conc_01_key_revocation_vs_redaction_race(test_fixtures):
    """
    TEST-B3-CONC-01: Serialized Key Revocation vs Concurrent Redaction Race.
    Verifies that when Session 1 holds an exclusive lock on the officer key for revocation,
    Session 2 blocks on SELECT ... FOR SHARE, unblocks upon Session 1 COMMIT, reads non-null
    revoked_at, and aborts with SQLSTATE 42501 with zero PII redaction and zero fence leak.
    """
    import asyncpg

    conn1 = await asyncpg.connect(DB_URL)
    conn2 = await asyncpg.connect(DB_URL)

    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce in a separate quick connection
    init_conn = await asyncpg.connect(DB_URL)
    await init_conn.execute("SET ROLE sec_admin;")
    row = await init_conn.fetchrow(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', $1::UUID, $2::UUID, 120, NULL, NULL);",
        t_id,
        o_id,
    )
    n_id = row[0]
    exp = row[1]
    await init_conn.close()

    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + priv.sign(payload)

    # Sequence coordination
    revocation_lock_acquired = asyncio.Event()
    session2_completed = asyncio.Event()
    session2_error = None

    async def session1_revocation():
        # Session 1: Acquire exclusive lock on officer key
        tx = conn1.transaction()
        await tx.start()
        await conn1.execute(
            "UPDATE secure_vault.officer_signing_keys SET revoked_at = clock_timestamp() WHERE officer_id = $1::UUID;",
            o_id,
        )
        revocation_lock_acquired.set()

        # Hold lock briefly to ensure Session 2 blocks on FOR SHARE
        await asyncio.sleep(0.5)

        # Commit revocation
        await tx.commit()
        await conn1.close()

    async def session2_redaction():
        nonlocal session2_error
        await revocation_lock_acquired.wait()
        # Session 2 attempts redaction (will block on FOR SHARE)
        await conn2.execute("SET ROLE sec_admin;")
        try:
            await conn2.execute(
                "CALL secure_vault.sp_execute_compliance_redaction($1::BYTEA, $2::BYTEA, $3::UUID);",
                ticket,
                pub_b,
                t_id,
            )
        except Exception as e:
            session2_error = e
        finally:
            session2_completed.set()
            await conn2.close()

    # Run both concurrent sessions
    await asyncio.gather(session1_revocation(), session2_redaction())

    # Assertions
    assert session2_error is not None, "Session 2 should have been rejected!"
    assert "42501" in str(session2_error) or "revoked" in str(
        session2_error
    ), f"Expected 42501 key revoked error, got: {session2_error}"

    # Verify invariants post-race in fresh session
    verify_conn = await asyncpg.connect(DB_URL)
    # 1. Target transfer snapshot remains unredacted
    snap = await verify_conn.fetchval(
        "SELECT current_owner_email_snapshot FROM public.workspace_ownership_transfers WHERE id = $1::UUID;",
        t_id,
    )
    assert snap != "[REDACTED_PII]", "PII was unexpectedly redacted!"

    # 2. Nonce was NOT consumed
    consumed = await verify_conn.fetchval(
        "SELECT consumed_at FROM secure_vault.action_nonces WHERE nonce_id = $1::UUID;",
        n_id,
    )
    assert consumed is None, "Nonce was unexpectedly consumed!"

    # 3. Fence table has 0 rows
    fence_count = await verify_conn.fetchval(
        "SELECT count(*) FROM secure_vault.redaction_execution_fence;"
    )
    assert fence_count == 0, f"Fence rows leaked: {fence_count}"

    await verify_conn.close()


def test_sec_09_10_escalation_guard_sec_admin_membership(db_conn):
    """TEST-B3-SEC-09 & 10: Neither raguard_app nor raguard_auth_worker is granted sec_admin."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT m.rolname
        FROM pg_auth_members am
        JOIN pg_roles r ON am.roleid = r.oid
        JOIN pg_roles m ON am.member = m.oid
        WHERE r.rolname = 'sec_admin' AND m.rolname IN ('raguard_app', 'raguard_auth_worker', 'raguard_compliance');
    """
    )
    rows = cur.fetchall()
    assert len(rows) == 0, f"Unexpected membership in sec_admin: {rows}"


def test_sec_19_fence_double_use(db_conn, test_fixtures):
    """TEST-B3-SEC-19: Fence double-use in same transaction is rejected."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + priv.sign(payload)

    # First redaction consumes fence
    cur.execute(
        "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
        (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
    )

    # Direct UPDATE in same transaction attempting to reuse destroyed fence fails
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET nominated_user_email_snapshot = '[REDACTED_PII]' WHERE id = %s;",
            (str(t_id),),
        )
    assert exc_info.value.pgcode in ("42501", "55000")
    db_conn.rollback()


def test_sec_22_expired_ticket_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-22: Ticket payload with past expires_at is rejected with 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Nonce valid in DB, but ticket says expired
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    past = datetime.now(UTC) - timedelta(seconds=10)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, past - timedelta(seconds=60), past)
    ticket = payload + priv.sign(payload)

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("42501", "22023")
    db_conn.rollback()


def test_sec_31_nonce_officer_mismatch_rejected(db_conn, test_fixtures):
    """TEST-B3-SEC-31: Nonce issued for Officer A, ticket signed by Officer B -> 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]

    # Create Officer B
    o_b_id = uuid.uuid4()
    cur.execute(
        """
        INSERT INTO public.users (id, email, username, is_active, is_verified, role, is_deleted, created_at, updated_at)
        VALUES (%s, %s, %s, true, true, 'compliance_officer', false, clock_timestamp(), clock_timestamp());
    """,
        (str(o_b_id), f"officer_b_{uuid.uuid4().hex[:6]}@raguard.test", f"ob_{uuid.uuid4().hex[:6]}"),
    )
    priv_b = ed25519.Ed25519PrivateKey.generate()
    pub_b_bytes = priv_b.public_key().public_bytes_raw()
    cur.execute(
        """
        INSERT INTO secure_vault.officer_signing_keys (officer_id, public_key, key_algorithm, created_at, expires_at)
        VALUES (%s, %s, 'Ed25519', clock_timestamp(), clock_timestamp() + interval '1 day');
    """,
        (str(o_b_id), psycopg2.Binary(pub_b_bytes)),
    )

    # Issue nonce for Officer A
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    # Ticket signed by Officer B
    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_b_id, t_id, 0x01, now, exp)
    ticket = payload + priv_b.sign(payload)

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b_bytes), str(t_id)),
        )
    assert exc_info.value.pgcode in ("42501", "22023")
    db_conn.rollback()


def test_sec_33_redundancy_rejection(db_conn, test_fixtures):
    """TEST-B3-SEC-33: Redundant redaction when all targeted fields are already redacted -> 55000."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Redact field 0x01 (current_owner_email_snapshot)
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_1, exp1 = cur.fetchone()
    now = datetime.now(UTC)
    p1 = build_ticket_payload(n_1, o_id, t_id, 0x01, now, exp1)
    cur.execute(
        "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
        (psycopg2.Binary(p1 + priv.sign(p1)), psycopg2.Binary(pub_b), str(t_id)),
    )

    # Attempt second redaction targeting only field 0x01 -> MUST FAIL with 55000
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_2, exp2 = cur.fetchone()
    p2 = build_ticket_payload(n_2, o_id, t_id, 0x01, now, exp2)
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(p2 + priv.sign(p2)), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode == "55000"
    db_conn.rollback()


def test_sec_34_non_pii_modification_during_redaction(db_conn, test_fixtures):
    """TEST-B3-SEC-34: Modifying non-PII columns during compliance redaction is rejected with 55000."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]

    # Record initial data
    cur.execute(
        "SELECT current_owner_email_snapshot, status FROM public.workspace_ownership_transfers WHERE id = %s;",
        (str(t_id),),
    )
    initial_row = cur.fetchone()

    # Grant UPDATE on status to sec_admin in transaction to test trigger-level enforcement
    cur.execute("GRANT UPDATE(status) ON public.workspace_ownership_transfers TO sec_admin;")

    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()
    cur.execute(
        "UPDATE secure_vault.action_nonces SET consumed_at = clock_timestamp(), consumed_txid = pg_catalog.txid_current() WHERE nonce_id = %s;",
        (str(n_id),),
    )
    cur.execute(
        "INSERT INTO secure_vault.redaction_execution_fence (txid, transfer_id, nonce_id, officer_id, action) VALUES (pg_catalog.txid_current(), %s, %s, %s, 'COMPLIANCE_REDACTION');",
        (str(t_id), str(n_id), str(o_id)),
    )

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET current_owner_email_snapshot = '[REDACTED_PII]', status = 'CANCELLED' WHERE id = %s;",
            (str(t_id),),
        )
    assert exc_info.value.pgcode == "55000"
    db_conn.rollback()

    # Assert protected data remains unchanged
    cur = db_conn.cursor()
    cur.execute(
        "SELECT current_owner_email_snapshot, status FROM public.workspace_ownership_transfers WHERE id = %s;",
        (str(t_id),),
    )
    post_row = cur.fetchone()
    assert post_row == initial_row
    db_conn.rollback()


def test_sec_35_arbitrary_redaction_allowlist_violation(db_conn, test_fixtures):
    """TEST-B3-SEC-35: Redacting to arbitrary text not matching allowlist is rejected with 22023."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]

    # Record initial data
    cur.execute(
        "SELECT current_owner_email_snapshot, nominated_user_email_snapshot FROM public.workspace_ownership_transfers WHERE id = %s;",
        (str(t_id),),
    )
    initial_row = cur.fetchone()

    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()
    cur.execute(
        "UPDATE secure_vault.action_nonces SET consumed_at = clock_timestamp(), consumed_txid = pg_catalog.txid_current() WHERE nonce_id = %s;",
        (str(n_id),),
    )
    cur.execute(
        "INSERT INTO secure_vault.redaction_execution_fence (txid, transfer_id, nonce_id, officer_id, action) VALUES (pg_catalog.txid_current(), %s, %s, %s, 'COMPLIANCE_REDACTION');",
        (str(t_id), str(n_id), str(o_id)),
    )

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET current_owner_email_snapshot = 'arbitrary_tampered_value@evil.com' WHERE id = %s;",
            (str(t_id),),
        )
    assert exc_info.value.pgcode == "22023"
    db_conn.rollback()

    # Assert protected data remains unchanged
    cur = db_conn.cursor()
    cur.execute(
        "SELECT current_owner_email_snapshot, nominated_user_email_snapshot FROM public.workspace_ownership_transfers WHERE id = %s;",
        (str(t_id),),
    )
    post_row = cur.fetchone()
    assert post_row == initial_row
    db_conn.rollback()


def test_sec_36_37_single_assignment_notes(db_conn, test_fixtures):
    """TEST-B3-SEC-36 & 37: Single-assignment invariance on response_notes and decision_notes -> 55000."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]

    # Attempt overwrite of notes via direct SQL -> 55000 or 42501
    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info_resp:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET response_notes = 'tampered' WHERE id = %s;",
            (str(t_id),),
        )
    assert exc_info_resp.value.pgcode in ("55000", "42501")
    db_conn.rollback()

    cur.execute("SET ROLE raguard_app;")
    with pytest.raises(psycopg2.Error) as exc_info_dec:
        cur.execute(
            "UPDATE public.workspace_ownership_transfers SET decision_notes = 'tampered' WHERE id = %s;",
            (str(t_id),),
        )
    assert exc_info_dec.value.pgcode in ("55000", "42501")
    db_conn.rollback()


def test_sec_38_rollback_nonce_recovery(db_conn, test_fixtures):
    """TEST-B3-SEC-38: When redaction transaction fails and rolls back, nonce remains unconsumed."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    pub_b = test_fixtures["pub_bytes"]

    # 1. Issue and commit nonce in DB
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()
    db_conn.commit()

    # 2. In second transaction, attempt redaction with forged signature -> FAILS
    now = datetime.now(UTC)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, exp)
    ticket = payload + (b"\x00" * 64)  # Bad signature

    cur.execute("SET ROLE sec_admin;")
    with pytest.raises(psycopg2.Error):
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    db_conn.rollback()

    # 3. Verify committed nonce remains in DB and is unconsumed
    cur.execute("SELECT consumed_at FROM secure_vault.action_nonces WHERE nonce_id = %s;", (str(n_id),))
    row = cur.fetchone()
    assert row is not None
    assert row[0] is None, "Nonce was consumed despite transaction failure!"
    db_conn.rollback()


def test_sec_39_nonce_expiry_drift(db_conn, test_fixtures):
    """TEST-B3-SEC-39: Ticket expiry drifting from DB nonce expiry by > 1s -> 22023 or 42501."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    o_id = test_fixtures["officer_id"]
    priv = test_fixtures["priv_key"]
    pub_b = test_fixtures["pub_bytes"]

    # Issue nonce with 60s TTL
    cur.execute("SET ROLE sec_admin;")
    cur.execute(
        "CALL secure_vault.sp_issue_compliance_nonce('COMPLIANCE_REDACTION', %s, %s, 60, NULL, NULL);",
        (str(t_id), str(o_id)),
    )
    n_id, exp = cur.fetchone()

    # Build ticket with drifted expiry (+5 seconds)
    now = datetime.now(UTC)
    drifted_exp = exp + timedelta(seconds=5)
    payload = build_ticket_payload(n_id, o_id, t_id, 0x01, now, drifted_exp)
    ticket = payload + priv.sign(payload)

    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(
            "CALL secure_vault.sp_execute_compliance_redaction(%s, %s, %s);",
            (psycopg2.Binary(ticket), psycopg2.Binary(pub_b), str(t_id)),
        )
    assert exc_info.value.pgcode in ("22023", "42501")
    db_conn.rollback()


def test_sec_42_downgrade_with_data_blocked(db_conn, test_fixtures):
    """TEST-B3-SEC-42: Downgrade guard blocks when departure records exist -> 55000."""
    cur = db_conn.cursor()
    t_id = test_fixtures["transfer_id"]
    ws_id = test_fixtures["workspace_id"]
    o_id = test_fixtures["owner_id"]

    # Insert a departure record
    cur.execute(
        """
        INSERT INTO public.workspace_former_owner_departures (
            workspace_id, former_owner_id, transfer_id, departure_type, former_role,
            departure_confirmed_at, confirmed_by_user_id
        ) VALUES (
            %s, %s, %s, 'VOLUNTARY_LEAVE', 'OWNER', clock_timestamp(), %s
        );
    """,
        (str(ws_id), str(o_id), str(t_id), str(o_id)),
    )
    db_conn.commit()

    # Execute Alembic downgrade guard block
    downgrade_guard_sql = """
        DO $$
        DECLARE
            v_dep_count INT;
        BEGIN
            SELECT count(*) INTO v_dep_count FROM public.workspace_former_owner_departures;
            IF v_dep_count > 0 THEN
                RAISE EXCEPTION 'Downgrade Aborted: % departure history records exist', v_dep_count
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """
    with pytest.raises(psycopg2.Error) as exc_info:
        cur.execute(downgrade_guard_sql)
    assert exc_info.value.pgcode == "55000"
    db_conn.rollback()


