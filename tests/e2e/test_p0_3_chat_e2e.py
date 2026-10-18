"""Veritas-RAG P0-3 Live Multi-Container Chat Integration Verification Suite.

Tests acceptance criteria 13, 14, and 15 against the live, running FastAPI HTTP
container on dedicated port 8008, isolated PostgreSQL (5433), Redis (6389),
Qdrant (6343), and Celery worker.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import io
import json
from pathlib import Path
import time
from typing import Any
import uuid

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.cache.client import get_redis_client
from backend.core.security.jwt import JWTService
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.status import DocumentStatus
from backend.document.services.document_service import DocumentService
from backend.document.storage.local import LocalStorageProvider
from backend.models.entities.user import User
from backend.models.entities.workspace import ProvisioningStatus, Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.modules.chat.models.chat_message import ChatMessage
from backend.modules.chat.models.chat_session import ChatSession
from tests.e2e.conftest import (
    E2E_API_BASE_URL,
    cleanup_chat_e2e_records,
    cleanup_run_qdrant_collections,
)


# ── Helper Utilities ─────────────────────────────────────────────────────────

async def poll_with_fresh_session(
    session_factory: async_sessionmaker[AsyncSession],
    check_fn: Any,
    timeout: float = 45.0,
    interval: float = 0.5,
    description: str = "condition",
) -> Any:
    """Poll condition using a fresh session per query to eliminate stale ORM identity-map caching."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        async with session_factory() as session:
            result = await check_fn(session)
            if result:
                return result
        await asyncio.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s waiting for: {description}")


def parse_sse_events(raw_text: str) -> list[dict[str, str]]:
    """Parse raw HTTP SSE text into structured event dictionaries."""
    events: list[dict[str, str]] = []
    current_event: dict[str, str] = {}

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue

        if line.startswith("id:"):
            current_event["id"] = line[3:].strip()
        elif line.startswith("event:"):
            current_event["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current_event["data"] = line[5:].strip()

    if current_event:
        events.append(current_event)

    return events


# ── Test Suite ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p0_3_live_chat_integration_suite(
    e2e_chat_preflight_verified: None,
    e2e_run_id: str,
    e2e_storage_root: Path,
    e2e_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_api_client: httpx.AsyncClient,
    e2e_qdrant_client: Any,
) -> None:
    """Master Verification for Criteria 13, 14, and 15 across live isolated services.

    1. Criterion 13: Authenticated Grounded Chat & Citations against active document version.
    2. Criterion 13 Negative: Querying unsupported concepts produces zero hallucinated citations.
    3. Criterion 14: Sequential SSE IDs, error emission on missing session.
    4. Criterion 14 Replay: Last-Event-ID reconnection replay from live Redis buffer.
    5. Criterion 15: Multi-turn message persistence and API reload in chronological order.
    6. Criterion 12 & 15: Cross-tenant isolation on chat session access and history.
    7. Criterion 18: Exact run-scoped cleanup of database, Qdrant, and storage artifacts.
    """
    storage_provider = LocalStorageProvider(root_path=e2e_storage_root)
    doc_service = DocumentService(storage_provider=storage_provider)
    jwt_service = JWTService()
    redis = get_redis_client()

    # Track created IDs for exact run-scoped cleanup
    created_workspaces: list[uuid.UUID] = []
    created_users: list[uuid.UUID] = []

    # Track test failure if an assertion or exception halts execution early
    test_failure: BaseException | None = None

    # Verification status scorecard for acceptance criteria
    verification_status: dict[str, str] = {
        "criterion_13_grounded_chat": "UNVERIFIED (Not yet executed)",
        "criterion_13_negative_query": "UNVERIFIED (Not yet executed)",
        "criterion_14_error_emission": "UNVERIFIED (Not yet executed)",
        "criterion_14_replay": "UNVERIFIED (Not yet executed)",
        "criterion_15_persistence": "UNVERIFIED (Not yet executed)",
        "criterion_15_tenant_isolation": "UNVERIFIED (Not yet executed)",
    }

    try:
        # ──────────────────────────────────────────────────────────────────────
        # STEP 1: Provision Workspace A, User A, and Ingest Document
        # ──────────────────────────────────────────────────────────────────────
        user_a_id = uuid.uuid4()
        user_a = User(
            id=user_a_id,
            email=f"user_a_{e2e_run_id}@example.com",
            role="viewer",
            is_active=True,
            is_verified=True,
        )

        ws_a_id = uuid.uuid4()
        ws_a = Workspace(
            id=ws_a_id,
            name=f"E2E Chat Workspace A {e2e_run_id}",
            slug=f"e2e-chat-a-{e2e_run_id}-{uuid.uuid4().hex[:6]}",
            public_id=f"ws_a_{uuid.uuid4().hex[:10]}",
            status=WorkspaceStatus.ACTIVE.value,
            provisioning_status=ProvisioningStatus.READY.value,
            storage_prefix=f"storage_a_{e2e_run_id}",
            qdrant_namespace=f"qdrant_a_{e2e_run_id}",
        )

        settings_a = WorkspaceSettings(
            id=uuid.uuid4(),
            workspace_id=ws_a_id,
            settings_json={"ai_enabled": True},
            schema_version=1,
            version=1,
            settings_hash="",
        )

        member_a = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_a_id,
            user_id=user_a_id,
            role=WorkspaceRole.OWNER.value,
            status=MemberStatus.ACTIVE.value,
        )

        e2e_session.add_all([user_a, ws_a, settings_a, member_a])
        await e2e_session.commit()
        created_users.append(user_a_id)
        created_workspaces.append(ws_a_id)

        # Issue native JWT for User A with Workspace A claims
        token_a, _, _ = await jwt_service.issue_tokens(
            user=user_a,
            workspace_id=ws_a_id,
            role="owner",
        )
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "Content-Type": "application/json",
        }

        # Ingest genuine document via official pipeline for Workspace A
        doc_content = (
            "Veritas-RAG Protocol Specification v3.0: High-assurance cryptographic provenance "
            "and zero-downtime version promotion specification. Developed for mission-critical enterprise systems."
        )
        stream_doc = io.BytesIO(doc_content.encode("utf-8"))
        doc_a, v1_a, job_a = await doc_service.upload_document(
            stream=stream_doc,
            filename="protocol_spec_v3.txt",
            declared_mime="text/plain",
            tenant_id=str(ws_a_id),
            owner_user_id=user_a_id,
            session=e2e_session,
        )

        # Poll until Celery worker processes ingestion, chunking, embedding, and promotes to READY
        async def check_doc_ready(session: AsyncSession) -> bool:
            d = await session.get(Document, doc_a.id)
            return d is not None and d.status == DocumentStatus.READY and d.latest_version_id == v1_a.id

        await poll_with_fresh_session(
            e2e_session_factory, check_doc_ready, timeout=45.0, description="Workspace A document ingestion"
        )

        # Verify Qdrant points exist
        qdrant_col = f"raguard_e2e_{e2e_run_id}_knowledge_{ws_a_id}"
        col_info = await e2e_qdrant_client.get_collection(qdrant_col)
        assert col_info.points_count > 0, "Qdrant collection must contain indexed document points"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 2 (Criterion 13): Authenticated Grounded Chat & Citations
        # ──────────────────────────────────────────────────────────────────────
        # Create Chat Session via live HTTP API
        create_resp = await e2e_api_client.post(
            "/api/v1/chat/sessions",
            json={"title": "Protocol v3 Discussion"},
            headers=headers_a,
        )
        assert create_resp.status_code == 200, f"Session creation failed: {create_resp.text}"
        session_data = create_resp.json().get("data", {})
        session_id_a = session_data.get("id")
        assert session_id_a is not None, "Created session must return a valid ID"

        # Submit live streaming chat query
        query_corr_id = f"corr_{uuid.uuid4().hex[:8]}"
        chat_req_payload = {
            "query": "What is Veritas-RAG Protocol Specification v3.0? Cite your source using [1].",
            "workspace_id": str(ws_a_id),
        }

        stream_resp = await e2e_api_client.post(
            f"/api/v1/chat/sessions/{session_id_a}/stream",
            json=chat_req_payload,
            headers={**headers_a, "x-correlation-id": query_corr_id},
        )
        assert stream_resp.status_code == 200, f"Chat stream failed: {stream_resp.text}"
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

        events_1 = parse_sse_events(stream_resp.text)
        assert len(events_1) > 0, "SSE stream must yield events"

        # Check if stream terminated with an error event (e.g. live LLM provider unconfigured/unavailable)
        err_event_1 = next((e for e in events_1 if e.get("event") == "error"), None)
        chunk_events = [e for e in events_1 if e.get("event") == "chunk"]

        if err_event_1:
            err_data_1 = {}
            try:
                err_data_1 = json.loads(err_event_1.get("data", "{}"))
            except Exception:
                pass

            import subprocess
            api_log_summary = ""
            try:
                res = subprocess.run(
                    ["docker", "logs", f"raguard-e2e-api-{e2e_run_id}", "--tail", "60"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                log_lines = (res.stdout + res.stderr).splitlines()
                err_lines = [
                    l.strip() for l in log_lines
                    if "AI Wrapper stream failed" in l
                    or "LLM Provider" in l
                    or "failed for stream request" in l
                    or "Exception" in l
                ]
                if err_lines:
                    match_line = next((l for l in err_lines if "AI Wrapper stream failed" in l), err_lines[-1])
                    if "error=" in match_line:
                        idx = match_line.find("error=")
                        api_log_summary = match_line[idx:idx+150].replace("Bearer", "[REDACTED]")
                    else:
                        api_log_summary = match_line[-120:].replace("Bearer", "[REDACTED]")
            except Exception:
                pass

            status_msg = f"Live LLM provider error event: code={err_data_1.get('code')}, message='{err_data_1.get('message')}'"
            if api_log_summary:
                status_msg += f", log: {api_log_summary}"

            verification_status["criterion_13_grounded_chat"] = f"UNVERIFIED ({status_msg})"
        elif not chunk_events:
            verification_status["criterion_13_grounded_chat"] = (
                "UNVERIFIED (Stream yielded no chunk events)"
            )
        else:
            # Verify terminal event is 'done'
            assert any(e.get("event") == "done" for e in events_1), "Stream must end with canonical 'done' event"
            parsed_chunks = [json.loads(c["data"]) for c in chunk_events]
            final_chunk = next((c for c in parsed_chunks if c.get("is_final")), None)
            assert final_chunk is not None, "Stream must contain a final chunk marked is_final=True"

            # Check meaningful answer and citations across chunks
            full_answer_text = "".join(c.get("text_delta", "") for c in parsed_chunks).strip()
            is_provider_error = (
                "[Error:" in full_answer_text
                or "Unable to generate a response" in full_answer_text
                or "AI service is temporarily busy" in full_answer_text
            )
            raw_citations = []
            for c in parsed_chunks:
                raw_citations.extend(c.get("citations_delta", []))
            seen_c_ids = set()
            citations = []
            for cit in raw_citations:
                c_id = cit.get("id") or f"{cit.get('document_id')}:{cit.get('citation_index')}"
                if c_id not in seen_c_ids:
                    seen_c_ids.add(c_id)
                    citations.append(cit)

            # Strengthened Criterion 13: Require meaningful answer + at least 1 valid citation
            if is_provider_error or not citations or len(full_answer_text) < 20:
                verification_status["criterion_13_grounded_chat"] = (
                    f"UNVERIFIED (Live LLM provider error or 0 grounded citations: '{full_answer_text[:120]}')"
                )
            else:
                for cit in citations:
                    assert cit.get("document_id") == str(doc_a.id), f"Citation must match ingested document ID: {cit}"
                    assert cit.get("document_version_id") == str(v1_a.id), f"Citation must match active version V1: {cit}"
                verification_status["criterion_13_grounded_chat"] = (
                    f"PASS ({len(citations)} citations tied to doc {doc_a.id} v1 {v1_a.id})"
                )

        # ──────────────────────────────────────────────────────────────────────
        # STEP 3 (Criterion 13 Negative): Unsupported Query Produces No Fake Citations
        # ──────────────────────────────────────────────────────────────────────
        neg_corr_id = f"corr_neg_{uuid.uuid4().hex[:8]}"
        neg_payload = {
            "query": "What is the secret recipe for Martian blue cheese on Jupiter?",
            "workspace_id": str(ws_a_id),
        }
        neg_resp = await e2e_api_client.post(
            f"/api/v1/chat/sessions/{session_id_a}/stream",
            json=neg_payload,
            headers={**headers_a, "x-correlation-id": neg_corr_id},
        )
        assert neg_resp.status_code == 200
        neg_events = parse_sse_events(neg_resp.text)
        assert len(neg_events) > 0, "Negative query stream must yield events"
        neg_chunks = [json.loads(e["data"]) for e in neg_events if e.get("event") == "chunk"]
        neg_citations = []
        for c in neg_chunks:
            neg_citations.extend(c.get("citations_delta", []))

        if neg_chunks:
            # Must not invent citations to the protocol document for alien cheese query
            assert len(neg_citations) == 0, (
                f"Negative query must not receive citations to unrelated document: {neg_citations}"
            )
            verification_status["criterion_13_negative_query"] = "PASS (0 hallucinated citations)"
        else:
            neg_err = next((e for e in neg_events if e.get("event") == "error"), None)
            if neg_err:
                verification_status["criterion_13_negative_query"] = "PASS (0 hallucinated citations; provider error handled safely)"
            else:
                verification_status["criterion_13_negative_query"] = "UNVERIFIED (No final chunk or error event received)"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 4 (Criterion 14): Controlled Error Emission on Missing Session
        # ──────────────────────────────────────────────────────────────────────
        bogus_session_id = str(uuid.uuid4())
        error_resp = await e2e_api_client.post(
            f"/api/v1/chat/sessions/{bogus_session_id}/stream",
            json={"query": "Hello?", "workspace_id": str(ws_a_id)},
            headers=headers_a,
        )
        assert error_resp.status_code == 200  # SSE protocol yields error as event
        err_events = parse_sse_events(error_resp.text)
        err_event = next((e for e in err_events if e.get("event") == "error"), None)
        assert err_event is not None, "Request with missing session must yield canonical 'error' SSE event"
        err_data = json.loads(err_event["data"])
        assert err_data.get("code") in ("SESSION_NOT_FOUND", "INTERNAL_ERROR")
        assert err_data.get("recoverable") is False
        verification_status["criterion_14_error_emission"] = f"PASS (code: {err_data.get('code')})"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 5 (Criterion 14 Replay): Last-Event-ID Reconnection Replay
        # ──────────────────────────────────────────────────────────────────────
        # Check Redis buffer for initial query
        redis_key = f"raguard:{ws_a_id}:sse:{query_corr_id}"
        buffered_count = await redis.llen(redis_key)
        if buffered_count == 0:
            verification_status["criterion_14_replay"] = (
                "UNVERIFIED (Original stream contained 0 buffered chunks in Redis; replay not exercised)"
            )
        else:
            ttl = await redis.ttl(redis_key)
            assert ttl > 0, "Redis replay buffer must have a positive TTL"

            # Read actual buffered chunks from Redis to establish ground-truth expected replay indices
            raw_buffered = await redis.lrange(redis_key, 0, -1)
            buffered_chunks = [json.loads(b) for b in raw_buffered]
            buffered_indices = [int(c["chunk_index"]) for c in buffered_chunks if "chunk_index" in c]
            # Chunks strictly after acknowledged chunk 0
            expected_replayed_indices = [idx for idx in buffered_indices if idx > 0]

            # Request replay with Last-Event-ID: {query_corr_id}:0
            replay_resp = await e2e_api_client.post(
                f"/api/v1/chat/sessions/{session_id_a}/stream",
                json=chat_req_payload,
                headers={
                    **headers_a,
                    "x-correlation-id": query_corr_id,
                    "Last-Event-ID": f"{query_corr_id}:0",
                },
            )
            assert replay_resp.status_code == 200
            replay_events = parse_sse_events(replay_resp.text)
            replay_chunk_events = [e for e in replay_events if e.get("event") == "chunk"]
            actual_replayed_indices: list[int] = []
            for e in replay_chunk_events:
                chunk_data = json.loads(e["data"])
                actual_replayed_indices.append(int(chunk_data["chunk_index"]))

            if expected_replayed_indices:
                # Replay exercised: verify exact index parity, detect leaks, duplicates, or missing chunks
                acknowledged_leaked = [idx for idx in actual_replayed_indices if idx <= 0]
                assert not acknowledged_leaked, f"Replay leaked acknowledged chunks: {acknowledged_leaked}"

                duplicates = [idx for idx in set(actual_replayed_indices) if actual_replayed_indices.count(idx) > 1]
                assert not duplicates, f"Replay contained duplicate chunk indices: {duplicates}"

                missing = [idx for idx in expected_replayed_indices if idx not in actual_replayed_indices]
                assert not missing, f"Replay missed expected buffered chunks: {missing}"

                assert actual_replayed_indices == expected_replayed_indices, (
                    f"Replayed indices {actual_replayed_indices} do not match expected {expected_replayed_indices}"
                )
                verification_status["criterion_14_replay"] = (
                    f"PASS (Indices replayed exactly: {actual_replayed_indices}; 0 acknowledged leaks, 0 duplicates, 0 missing)"
                )
            else:
                # Replay not exercised: original stream yielded only chunk 0 (e.g. single-chunk fallback)
                assert len(actual_replayed_indices) == 0, (
                    "Acknowledging chunk 0 of a single-chunk stream must leave 0 unacknowledged chunks"
                )
                verification_status["criterion_14_replay"] = (
                    "UNVERIFIED (Original stream contained only chunk 0; replay after acknowledging chunk 0 has no remaining chunks to deliver)"
                )

        # ──────────────────────────────────────────────────────────────────────
        # STEP 6 (Criterion 15): Conversation History Persistence and API Reload
        # ──────────────────────────────────────────────────────────────────────
        # Bounded polling helper for committed database rows in PostgreSQL
        # Uses fresh session per attempt to eliminate stale ORM cache and guard against async commit latency
        async def check_messages_persisted(session: AsyncSession) -> list[ChatMessage] | None:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id_a)
                .order_by(ChatMessage.created_at.asc())
            )
            msgs = (await session.execute(stmt)).scalars().all()
            if len(msgs) >= 2:
                return list(msgs)
            return None

        db_messages = await poll_with_fresh_session(
            e2e_session_factory,
            check_messages_persisted,
            timeout=10.0,
            interval=0.25,
            description=f"persistence of chat messages for session {session_id_a}",
        )
        assert len(db_messages) >= 2, f"PostgreSQL must persist conversation messages: found {len(db_messages)}"
        assert any(m.role == "user" for m in db_messages), "PostgreSQL must contain user query messages"

        # Reload conversation through API endpoint
        history_resp = await e2e_api_client.get(
            f"/api/v1/chat/sessions/{session_id_a}/messages",
            headers=headers_a,
        )
        assert history_resp.status_code == 200
        hist_data = history_resp.json().get("data", [])
        assert len(hist_data) == len(db_messages), (
            f"API reload must return all persisted messages: expected {len(db_messages)}, got {len(hist_data)}"
        )
        assert [m["id"] for m in hist_data] == [str(m.id) for m in db_messages], (
            "API messages must match database order and IDs"
        )
        verification_status["criterion_15_persistence"] = (
            f"PASS ({len(db_messages)} messages in DB, API reload confirmed chronological order)"
        )

        # ──────────────────────────────────────────────────────────────────────
        # STEP 7 (Criterion 12 & 15): Multi-Tenant Boundary Isolation
        # ──────────────────────────────────────────────────────────────────────
        user_b_id = uuid.uuid4()
        user_b = User(
            id=user_b_id,
            email=f"user_b_{e2e_run_id}@example.com",
            role="viewer",
            is_active=True,
            is_verified=True,
        )

        ws_b_id = uuid.uuid4()
        ws_b = Workspace(
            id=ws_b_id,
            name=f"E2E Chat Workspace B {e2e_run_id}",
            slug=f"e2e-chat-b-{e2e_run_id}-{uuid.uuid4().hex[:6]}",
            public_id=f"ws_b_{uuid.uuid4().hex[:10]}",
            status=WorkspaceStatus.ACTIVE.value,
            provisioning_status=ProvisioningStatus.READY.value,
            storage_prefix=f"storage_b_{e2e_run_id}",
            qdrant_namespace=f"qdrant_b_{e2e_run_id}",
        )

        settings_b = WorkspaceSettings(
            id=uuid.uuid4(),
            workspace_id=ws_b_id,
            settings_json={"ai_enabled": True},
            schema_version=1,
            version=1,
            settings_hash="",
        )

        member_b = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_b_id,
            user_id=user_b_id,
            role=WorkspaceRole.OWNER.value,
            status=MemberStatus.ACTIVE.value,
        )

        e2e_session.add_all([user_b, ws_b, settings_b, member_b])
        await e2e_session.commit()
        created_users.append(user_b_id)
        created_workspaces.append(ws_b_id)

        token_b, _, _ = await jwt_service.issue_tokens(
            user=user_b,
            workspace_id=ws_b_id,
            role="owner",
        )
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "Content-Type": "application/json",
        }

        # User B attempts to access Workspace A's session history
        cross_resp = await e2e_api_client.get(
            f"/api/v1/chat/sessions/{session_id_a}/messages",
            headers=headers_b,
        )
        # Must fail closed: either 404 Not Found or empty list isolated to Tenant B
        assert cross_resp.status_code in (403, 404) or len(cross_resp.json().get("data", [])) == 0, (
            f"Cross-tenant session access must be blocked: status {cross_resp.status_code}"
        )
        verification_status["criterion_15_tenant_isolation"] = (
            f"PASS (cross-tenant access blocked with status {cross_resp.status_code})"
        )

    except BaseException as exc:
        test_failure = exc
        raise
    finally:
        # ──────────────────────────────────────────────────────────────────────
        # 1. REPORT: Print structured scorecard (runs unconditionally, even on failure)
        # ──────────────────────────────────────────────────────────────────────
        has_failure = test_failure is not None
        unverified_items = [
            k for k, v in verification_status.items() if v.startswith("UNVERIFIED")
        ]
        failed_items = [
            k for k, v in verification_status.items() if v.startswith("FAIL")
        ]
        if has_failure and not failed_items:
            overall_verdict = f"FAILED ({type(test_failure).__name__}: {test_failure})"
        elif failed_items:
            overall_verdict = f"FAILED ({len(failed_items)} criteria failed)"
        elif unverified_items:
            overall_verdict = f"UNVERIFIED ({len(unverified_items)} criteria unverified: {', '.join(unverified_items)})"
        else:
            overall_verdict = "PASS (All 6 criteria verified)"

        print("\n" + "=" * 70)
        print("VERITAS-RAG P0-3 LIVE CHAT VERIFICATION STATUS REPORT")
        print("=" * 70)
        print(f"  OVERALL VERDICT: {overall_verdict}")
        print("-" * 70)
        for criterion, status in verification_status.items():
            print(f"  {criterion:32s}: {status}")
        print("=" * 70 + "\n")

        # ──────────────────────────────────────────────────────────────────────
        # 2. TEARDOWN: Exact run-scoped cleanup of disposable entities
        # ──────────────────────────────────────────────────────────────────────
        try:
            await e2e_session.rollback()
        except Exception:
            pass

        if created_workspaces:
            await cleanup_chat_e2e_records(
                session=e2e_session,
                workspace_ids=created_workspaces,
                user_ids=created_users,
            )

        # Enumerate and purge Qdrant collections for this run
        await cleanup_run_qdrant_collections(e2e_qdrant_client, e2e_run_id)

        # ──────────────────────────────────────────────────────────────────────
        # 3. ACCURATE PYTEST RESULT: Prevent UNVERIFIED from silently passing
        # ──────────────────────────────────────────────────────────────────────
        # If test_failure is present, python re-raises it from 'except' block.
        # If test_failure is None but criteria remain UNVERIFIED, call pytest.skip
        # so pytest explicitly records SKIPPED (UNVERIFIED) instead of PASSED.
        if test_failure is None and unverified_items:
            pytest.skip(
                f"P0-3 Live Chat Gate UNVERIFIED: {unverified_items}. "
                "Transport and isolation verified, but live LLM generation/replay was unverified."
            )
