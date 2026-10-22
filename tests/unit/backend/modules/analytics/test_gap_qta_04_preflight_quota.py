"""Deterministic Unit Tests for GAP-QTA-04 Preflight Quota Governance.

Verifies:
1. One token remaining blocks large completion requests.
2. Exhausted quota blocks even with zero-token requested estimate.
3. Negative and malformed token estimates raise ValueError / HTTP 400 / 422.
4. Preflight dynamic token estimation from query and max_answer_tokens.
5. Embedding batch token estimate halts with EMB_002 on budget exhaustion before vectorization.
6. Direct generation routes (/generate/grounded and /generate/stream) enforce quota and reject missing workspace context.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.quota import enforce_workspace_quota
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.core.exceptions import ApplicationException
from backend.core.permissions.rbac import Role
from backend.modules.analytics.services.quota import QuotaGovernor
from backend.modules.embedding.schemas.errors import TokenQuotaExceededError
from backend.modules.embedding.services.embedding_service import EmbeddingService
from backend.modules.generation.api.routes import router as gen_router
from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTO,
    GenerationRequestDTOv2,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


@pytest.mark.asyncio
async def test_gap_qta_04_one_token_remaining_blocks_large_completion():
    """Verify that when 1 token remains, a large completion preflight request is blocked."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()

    mock_quota = MagicMock()
    mock_quota.monthly_token_limit = 10000
    mock_quota.monthly_budget_usd = 100.0
    mock_quota.warning_threshold_pct = 80
    mock_quota.is_hard_enforced = True

    with patch.object(governor, "get_quota_settings", new_callable=AsyncMock) as mock_get_settings, \
         patch.object(governor, "get_durable_usage", new_callable=AsyncMock) as mock_get_usage:
        mock_get_settings.return_value = mock_quota
        # 1 token remaining: 9999 used of 10000 limit
        mock_get_usage.return_value = 9999

        # Request with 1024 tokens estimate
        res = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            requested_tokens=1024,
        )

        assert not res.is_allowed
        assert res.blocked_by == "workspace_quota"
        assert "Workspace token budget exhausted" in res.detail


@pytest.mark.asyncio
async def test_gap_qta_04_exhausted_quota_blocks_zero_token_request():
    """Verify that when quota is at or above limit, even requested_tokens=0 is blocked."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()

    mock_quota = MagicMock()
    mock_quota.monthly_token_limit = 10000
    mock_quota.is_hard_enforced = True

    with patch.object(governor, "get_quota_settings", new_callable=AsyncMock) as mock_get_settings, \
         patch.object(governor, "get_durable_usage", new_callable=AsyncMock) as mock_get_usage:
        mock_get_settings.return_value = mock_quota
        mock_get_usage.return_value = 10000  # Exactly at limit

        res = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            requested_tokens=0,
        )

        assert not res.is_allowed
        assert res.blocked_by == "workspace_quota"


@pytest.mark.asyncio
async def test_gap_qta_04_negative_or_malformed_token_estimate_raises_error():
    """Verify check_hierarchical_quota rejects negative or non-integer requested_tokens."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()

    # Negative tokens must raise ValueError
    with pytest.raises(ValueError, match="requested_tokens must be a non-negative integer"):
        await governor.check_hierarchical_quota(workspace_id=ws_id, requested_tokens=-50)

    # Malformed non-integer tokens must raise ValueError
    with pytest.raises(ValueError, match="requested_tokens must be a non-negative integer"):
        await governor.check_hierarchical_quota(workspace_id=ws_id, requested_tokens="1000")  # type: ignore


@pytest.mark.asyncio
async def test_gap_qta_04_enforce_workspace_quota_negative_parameter_raises_http_400():
    """Verify enforce_workspace_quota rejects negative explicit estimate with HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        enforce_workspace_quota(est_tokens=-10)

    assert exc_info.value.status_code == 400
    assert "must be a positive integer" in exc_info.value.detail


@pytest.mark.asyncio
async def test_gap_qta_04_enforce_workspace_quota_rejects_invalid_max_answer_tokens():
    """Verify dependency rejects payload with max_answer_tokens <= 0 with HTTP 422."""
    guard = enforce_workspace_quota()

    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(
        return_value=b'{"query": "Test query", "max_answer_tokens": -50}'
    )

    mock_user = MagicMock(spec=UserContext)
    mock_user.id = uuid.uuid4()
    mock_user.workspace_id = uuid.uuid4()
    mock_user.tenant_id = str(mock_user.workspace_id)

    mock_session = AsyncMock()

    with patch("backend.core.dependencies.quota.get_workspace_member_or_raise", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await guard(
                request=mock_request,
                workspace_id=mock_user.workspace_id,
                current_user=mock_user,
                session=mock_session,
            )

        assert exc_info.value.status_code == 422
        assert "max_answer_tokens must be a positive integer" in exc_info.value.detail


@pytest.mark.asyncio
async def test_gap_qta_04_embedding_batch_preflight_blocks_before_provider():
    """Verify embedding batch calculation halts with EMB_002 when batch exceeds balance."""
    mock_repo = MagicMock()
    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    mock_job.provider = "openai"
    mock_job.model_name = "text-embedding-3-small"
    mock_job.document_version_id = uuid.uuid4()
    mock_repo.get_job_by_id_and_tenant = AsyncMock(return_value=mock_job)
    mock_repo.update_job_progress = AsyncMock()
    mock_chunk = MagicMock(content="A" * 4000, content_hash="hash123")  # ~1000 tokens
    mock_repo.get_unembedded_chunks = AsyncMock(return_value=[mock_chunk])
    mock_repo.get_existing_embeddings_by_hashes = AsyncMock(return_value={})
    mock_repo.session = MagicMock()

    service = EmbeddingService(repository=mock_repo)

    ws_id = uuid.uuid4()

    # Quota check returns used=9500, limit=10000, hard_enforced=True
    # est_batch_tokens = 1000. 9500 + 1000 = 10500 > 10000 -> Exceeded!
    with patch("backend.modules.analytics.services.quota.QuotaGovernor.check_quota", new_callable=AsyncMock) as mock_check_q:
        mock_check_q.return_value = (False, 9500, 10000, True)

        with pytest.raises(TokenQuotaExceededError) as exc_info:
            await service.process_embedding_batch(
                job_id=mock_job.id,
                tenant_id=str(ws_id),
                batch_size=10,
            )

        assert "token quota exceeded" in str(exc_info.value)
        assert exc_info.value.code == "EMB_002"


@pytest.mark.asyncio
async def test_gap_qta_04_direct_generation_routes_enforce_quota():
    """Verify direct generation endpoints enforce quota and reject over-budget requests with 429."""
    app = FastAPI()
    app.include_router(gen_router, prefix="/api/v1")

    ws_id = uuid.uuid4()
    auth_user = UserContext(
        id=uuid.uuid4(),
        email="admin@veritas.ai",
        role=Role.PLATFORM_ADMIN,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: auth_user
    async def override_get_db():
        yield AsyncMock()
    app.dependency_overrides[get_db] = override_get_db

    # Mock QuotaGovernor.check_hierarchical_quota to return exhausted
    with patch("backend.modules.generation.api.routes.QuotaGovernor.check_hierarchical_quota", new_callable=AsyncMock) as mock_quota:
        mock_res = MagicMock()
        mock_res.is_allowed = False
        mock_res.blocked_by = "workspace_quota"
        mock_res.detail = "Workspace token budget exhausted"
        mock_quota.return_value = mock_res

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. /generate/stream
            resp_stream = await client.post(
                "/api/v1/generate/stream",
                json={
                    "query": "What is the security policy?",
                    "evidence_chunks": [],
                    "correlation_id": "c1",
                    "workspace_id": str(ws_id),
                    "tenant_id": str(ws_id),
                    "stream": True,
                },
            )
            assert resp_stream.status_code == 429
            assert "Workspace token budget exhausted" in resp_stream.json().get("detail", "")

            # 2. /generate/grounded
            resp_grounded = await client.post(
                "/api/v1/generate/grounded",
                json={
                    "query": "What is the security policy?",
                    "evidence_chunks": [],
                    "correlation_id": "c2",
                    "workspace_id": str(ws_id),
                    "tenant_id": str(ws_id),
                },
            )
            assert resp_grounded.status_code == 429
            assert "Workspace token budget exhausted" in resp_grounded.json().get("detail", "")


@pytest.mark.asyncio
async def test_gap_qta_04_direct_generation_rejects_missing_workspace_context():
    """Verify direct generation rejects with HTTP 400 when workspace context cannot be resolved."""
    app = FastAPI()
    app.include_router(gen_router, prefix="/api/v1")

    # User with no workspace or tenant
    auth_user = UserContext(
        id=uuid.uuid4(),
        email="noworkspace@veritas.ai",
        role=Role.MEMBER,
        workspace_id=None,
        tenant_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: auth_user
    async def override_get_db():
        yield AsyncMock()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Request without tenant_id or workspace_id
        resp = await client.post(
            "/api/v1/generate/grounded",
            json={
                "query": "Valid query text",
                "evidence_chunks": [],
                "correlation_id": "c3",
            },
        )
        assert resp.status_code == 400
        assert "Missing workspace or tenant context" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_finding_wp3b_sec_01_anonymous_request_rejected_with_401():
    """FINDING-WP3B-SEC-01: Anonymous requests to direct generation routes receive HTTP 401."""
    app = FastAPI()
    app.include_router(gen_router, prefix="/api/v1")

    @app.exception_handler(ApplicationException)
    async def handle_application_exception(request, exc: ApplicationException):
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/generate/grounded",
            json={
                "query": "Valid query",
                "evidence_chunks": [],
                "correlation_id": "c_anon",
                "workspace_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401
        assert resp.json().get("error_code") == "AUTH_001"


@pytest.mark.asyncio
async def test_finding_wp3b_sec_01_cross_workspace_rejected_with_403():
    """FINDING-WP3B-SEC-01: Authenticated user targeting another workspace is blocked with HTTP 403."""
    app = FastAPI()
    app.include_router(gen_router, prefix="/api/v1")

    caller_user = UserContext(
        id=uuid.uuid4(),
        email="caller@veritas.ai",
        role=Role.VIEWER,
        workspace_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: caller_user
    async def override_get_db():
        yield AsyncMock()
    app.dependency_overrides[get_db] = override_get_db

    target_ws = uuid.uuid4()

    with patch("backend.modules.generation.api.routes.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth:
        mock_auth.side_effect = HTTPException(
            status_code=403,
            detail="Forbidden: You are not an active member of this workspace.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/generate/grounded",
                json={
                    "query": "Targeting Workspace B",
                    "evidence_chunks": [],
                    "correlation_id": "c_cross_ws",
                    "workspace_id": str(target_ws),
                },
            )
            assert resp.status_code == 403
            assert "Forbidden: You are not an active member" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_finding_wp3b_sec_01_get_workspace_member_canonical_contract():
    """FINDING-WP3B-SEC-01: Verify canonical get_workspace_member_or_raise enforces membership."""
    session = AsyncMock()
    user = UserContext(id=uuid.uuid4(), email="member@veritas.ai", role=Role.MEMBER)
    target_ws = uuid.uuid4()

    # 1. Non-member -> raises 403
    with patch("backend.core.dependencies.workspace.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await get_workspace_member_or_raise(target_ws, user, session)
        assert exc_info.value.status_code == 403
        assert "not an active member" in exc_info.value.detail

    # 2. Platform Admin -> exempt from membership check
    admin_user = UserContext(id=uuid.uuid4(), email="admin@veritas.ai", role=Role.PLATFORM_ADMIN)
    result = await get_workspace_member_or_raise(target_ws, admin_user, session)
    assert result is None  # Allowed


@pytest.mark.asyncio
async def test_finding_wp3b_qta_01_streaming_generation_propagates_max_output_tokens():
    """FINDING-WP3B-QTA-01: Verify max_answer_tokens is propagated as max_output_tokens in LLMRequest."""
    mock_provider = MagicMock()
    captured_requests = []

    async def mock_stream(llm_req):
        captured_requests.append(llm_req)
        yield "Answer tokens."

    mock_provider.stream = mock_stream

    service = StreamingGroundedGenerationService(
        citation_extractor=CitationExtractor(),
        prompt_guard=PromptGuard(),
        llm_provider=mock_provider,
    )

    evidence = [
        RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            tenant_id="test",
            content="Veritas-RAG enforces token quotas across all workspaces.",
            rrf_score=0.95,
            final_rank=1,
            score=0.95,
            rerank_score=0.95,
            dense_score=0.95,
            sparse_score=0.90,
            source_type="file_upload",
        )
    ]

    req = GenerationRequestDTOv2(
        query="Verify output token propagation.",
        evidence_chunks=evidence,
        correlation_id="c_qta_prop",
        tenant_id=str(uuid.uuid4()),
        max_answer_tokens=768,
        stream=True,
    )

    chunks = [c async for c in service.generate_stream(req)]
    assert len(captured_requests) == 1
    assert captured_requests[0].max_output_tokens == 768
