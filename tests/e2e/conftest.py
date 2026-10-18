"""Pytest fixtures and environment configuration for Veritas-RAG P0-3 E2E testing.

Enforces fail-closed isolation across database, Redis broker, Qdrant vectors,
and worker processes with strict identity verification and verifiable cleanup.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import httpx
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
import uuid

import pytest
import pytest_asyncio
from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings
from backend.tasks.celery_app import celery_app


# ── 1. Execution Run Identifier & Port Definitions ───────────────────────────
RUN_ID = os.environ.get("RUN_ID") or f"e2e_{int(time.time())}_{uuid.uuid4().hex[:6]}"
os.environ["RUN_ID"] = RUN_ID

E2E_POSTGRES_PORT = int(os.environ.get("E2E_POSTGRES_PORT", "5433"))
E2E_REDIS_PORT = int(os.environ.get("E2E_REDIS_PORT", "6389"))
E2E_QDRANT_PORT = int(os.environ.get("E2E_QDRANT_PORT", "6343"))
E2E_QDRANT_GRPC_PORT = int(os.environ.get("E2E_QDRANT_GRPC_PORT", "6344"))
E2E_API_PORT = int(os.environ.get("E2E_API_PORT", "8008"))
E2E_API_BASE_URL = f"http://localhost:{E2E_API_PORT}"

# Configure runner environment to point strictly to dedicated E2E ports
E2E_DB_URL = f"postgresql+asyncpg://postgres:postgres@localhost:{E2E_POSTGRES_PORT}/raguard_test_db"
E2E_CELERY_BROKER = f"redis://localhost:{E2E_REDIS_PORT}/0"
E2E_CELERY_BACKEND = f"redis://localhost:{E2E_REDIS_PORT}/1"
E2E_QDRANT_PREFIX = f"raguard_e2e_{RUN_ID}"

# Host storage scratch path mounted into container
E2E_STORAGE_HOST_DIR = Path(f"./scratch/e2e_storage_{RUN_ID}").resolve()

os.environ["DATABASE_URL"] = E2E_DB_URL
os.environ["TEST_DATABASE_URL"] = E2E_DB_URL
os.environ["ALEMBIC_DATABASE_URL"] = f"postgresql://postgres:postgres@localhost:{E2E_POSTGRES_PORT}/raguard_test_db"
os.environ["CELERY_BROKER_URL"] = E2E_CELERY_BROKER
os.environ["CELERY_RESULT_BACKEND"] = E2E_CELERY_BACKEND
os.environ["REDIS_URL"] = E2E_CELERY_BROKER
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = str(E2E_QDRANT_PORT)
os.environ["QDRANT_GRPC_PORT"] = str(E2E_QDRANT_GRPC_PORT)
os.environ["QDRANT_COLLECTION_PREFIX"] = E2E_QDRANT_PREFIX
os.environ["DEFAULT_EMBEDDING_PROVIDER"] = "local"

# Refresh cached settings
get_settings.cache_clear()


# ── 2. Runner & Worker Identity and Schema Verification ───────────────────────

SENTINEL_TABLE = "_e2e_run_sentinel"


def get_postgres_container_cluster_id(postgres_container_name: str) -> str:
    """Retrieve the immutable PostgreSQL cluster system_identifier directly from the live container.

    This 64-bit identifier is generated at initdb time and stored in pg_control. It uniquely identifies
    the container's database cluster and cannot be forged by any other database instance.
    """
    cmd = [
        "docker", "exec", postgres_container_name,
        "psql", "-U", "postgres", "-d", "raguard_test_db", "-t", "-A",
        "-c", "SELECT system_identifier::text FROM pg_control_system();"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        sys_id = proc.stdout.strip()
        if not sys_id or not sys_id.isdigit():
            raise RuntimeError(f"Invalid cluster system_identifier from container '{postgres_container_name}': '{sys_id}'")
        return sys_id
    except Exception as exc:
        raise RuntimeError(
            f"FATAL: Failed to query system_identifier from postgres container '{postgres_container_name}': {exc}"
        ) from exc


async def initialize_and_verify_database_sentinel(
    engine: Any, postgres_container_name: str, run_id: str
) -> str:
    """Establish and verify a run-specific sentinel row in the isolated PostgreSQL instance.

    Guarantees that both runner and worker are bound to the exact same disposable
    database instance for this specific RUN_ID and not any pre-existing database.
    """
    # 1. Retrieve the ground-truth cluster system_identifier directly from the container
    expected_cluster_id = get_postgres_container_cluster_id(postgres_container_name)

    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                res = await conn.execute(text("""
                    SELECT current_database(), inet_server_port(), system_identifier::text
                    FROM pg_control_system(), (SELECT current_database(), inet_server_port()) AS s;
                """))
                row = res.fetchone()
                if not row:
                    raise RuntimeError("CRITICAL: Failed to query runner database identity.")
                db_name, server_port, runner_cluster_id = row
                if db_name != "raguard_test_db" or int(server_port) != 5432:
                    raise RuntimeError(
                        f"FATAL SAFETY VIOLATION: Runner database identity mismatch. "
                        f"Expected ('raguard_test_db', 5432), got ('{db_name}', {server_port}). "
                        f"Execution strictly restricted to 'raguard_test_db'."
                    )
                if runner_cluster_id != expected_cluster_id:
                    raise RuntimeError(
                        f"FATAL INSTANCE IDENTITY MISMATCH: Runner is connected to PostgreSQL cluster '{runner_cluster_id}', "
                        f"but isolated container '{postgres_container_name}' has cluster '{expected_cluster_id}'. "
                        f"Runner is connected to the wrong PostgreSQL instance!"
                    )

                # Create sentinel table if not present
                await conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {SENTINEL_TABLE} (
                        run_id VARCHAR(100) PRIMARY KEY,
                        cluster_id VARCHAR(100) NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT clock_timestamp()
                    );
                """))

                # Verify no conflicting run sentinels exist
                check = await conn.execute(text(f"SELECT run_id, cluster_id FROM {SENTINEL_TABLE}"))
                rows = check.fetchall()
                existing_runs = [r[0] for r in rows]
                if existing_runs and existing_runs != [run_id]:
                    raise RuntimeError(
                        f"FATAL COLLISION: Unexpected sentinel run_ids {existing_runs} found in {SENTINEL_TABLE}. "
                        f"Expected exclusively '{run_id}'."
                    )

                # Upsert current run sentinel
                if run_id not in existing_runs:
                    await conn.execute(
                        text(f"INSERT INTO {SENTINEL_TABLE} (run_id, cluster_id) VALUES (:run_id, :cluster_id)"),
                        {"run_id": run_id, "cluster_id": expected_cluster_id},
                    )

            return expected_cluster_id
        except (ConnectionResetError, ConnectionRefusedError, OSError) as exc:
            if attempt == 4:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))

    return expected_cluster_id


def verify_worker_database_identity(
    worker_container_name: str, expected_cluster_id: str, expected_run_id: str
) -> None:
    """Probe the live worker container via docker exec to verify its database identity and sentinel.

    Uses the actual container environment without modifying any production task definitions.
    Fails closed if the worker container does not connect strictly to raguard_test_db on port 5432,
    match the ground-truth cluster system_identifier, AND observe the exact run sentinel.
    """
    probe_code = (
        "import asyncio, json, os\n"
        "from backend.database.engine import get_session_factory\n"
        "from sqlalchemy import text\n"
        "async def probe():\n"
        "    factory = get_session_factory()\n"
        "    async with factory() as session:\n"
        "        res = await session.execute(text("
        "            'SELECT current_database(), inet_server_port(), system_identifier::text "
        "             FROM pg_control_system(), (SELECT current_database(), inet_server_port()) AS s;'"
        "        ))\n"
        "        row = res.fetchone()\n"
        "        db_url = os.environ.get('DATABASE_URL', '')\n"
        "        sentinel_res = await session.execute(text('SELECT run_id, cluster_id FROM _e2e_run_sentinel;'))\n"
        "        sentinels = [f'{r[0]}={r[1]}' for r in sentinel_res.fetchall()]\n"
        "        sentinel_str = ','.join(sentinels)\n"
        "        data = {'db': str(row[0]), 'port': str(row[1]), 'url': db_url, 'cluster_id': str(row[2]), 'sentinels': sentinel_str}\n"
        "        print('SENTINEL_PROBE:' + json.dumps(data))\n"
        "asyncio.run(probe())"
    )
    cmd = ["docker", "exec", worker_container_name, "python", "-c", probe_code]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        probe_line = ""
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("SENTINEL_PROBE:"):
                probe_line = line_str[len("SENTINEL_PROBE:"):]
                break
        if not probe_line:
            raise RuntimeError(f"SENTINEL_PROBE marker not found in worker probe response: '{proc.stdout.strip()}'")
        payload = json.loads(probe_line)
        worker_db = payload["db"]
        worker_port = payload["port"]
        worker_db_url = payload["url"]
        worker_cluster_id = payload["cluster_id"]
        worker_sentinels = payload["sentinels"]
        if worker_db != "raguard_test_db" or worker_port != "5432" or "raguard_test_db" not in worker_db_url:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Worker container '{worker_container_name}' identity mismatch. "
                f"Expected db='raguard_test_db', port='5432', URL containing 'raguard_test_db'. "
                f"Got db='{worker_db}', port='{worker_port}', url='{worker_db_url}'."
            )
        if worker_cluster_id != expected_cluster_id:
            raise RuntimeError(
                f"FATAL INSTANCE IDENTITY MISMATCH: Worker container is connected to PostgreSQL cluster '{worker_cluster_id}', "
                f"expected container cluster '{expected_cluster_id}'. Worker is connected to the wrong database instance!"
            )
        sentinel_map = dict(s.split("=", 1) for s in worker_sentinels.split(",") if "=" in s)
        if expected_run_id not in sentinel_map or sentinel_map[expected_run_id] != expected_cluster_id:
            raise RuntimeError(
                f"FATAL INSTANCE IDENTITY MISMATCH: Worker container observed sentinels: {sentinel_map}. "
                f"Expected run_id='{expected_run_id}' with cluster_id='{expected_cluster_id}'."
            )
    except Exception as exc:
        raise RuntimeError(
            f"FATAL: Worker container database probe failed for '{worker_container_name}': {exc}"
        ) from exc


async def verify_schema_readiness(engine: Any) -> None:
    """Verify that required core tables exist before executing any test code."""
    for attempt in range(5):
        try:
            async with engine.connect() as conn:
                res = await conn.execute(text("""
                    SELECT
                        to_regclass('public.documents'),
                        to_regclass('public.document_versions'),
                        to_regclass('public.document_chunks'),
                        to_regclass('public.processing_jobs')
                """))
                row = res.fetchone()
                if not row or any(t is None for t in row):
                    raise RuntimeError(
                        f"FATAL: Database schema incomplete. Required tables missing: {row}. "
                        "Migrations must be applied successfully before running E2E tests."
                    )
            return
        except (ConnectionResetError, ConnectionRefusedError, OSError) as exc:
            if attempt == 4:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))


def verify_worker_live(celery_app_instance: Any, timeout: float = 15.0) -> None:
    """Verify that an active Celery worker is connected to the isolated E2E Redis broker."""
    start = time.perf_counter()
    last_err = None
    while time.perf_counter() - start < timeout:
        try:
            inspector = celery_app_instance.control.inspect(timeout=2.0)
            if inspector:
                stats = inspector.stats()
                if stats:
                    return
        except Exception as exc:
            last_err = exc
        time.sleep(1.0)

    raise RuntimeError(
        f"FATAL: No active Celery worker detected on E2E Redis broker within {timeout}s (last error: {last_err})."
    )


def verify_worker_provenance(worker_container_name: str) -> None:
    """Verify that the worker container is running the expected immutable image ID and provenance digest.

    Fails closed if either E2E_WORKER_IMAGE_ID or E2E_SOURCE_DIGEST does not match the live container.
    """
    expected_image_id = os.environ.get("E2E_WORKER_IMAGE_ID")
    expected_digest = os.environ.get("E2E_SOURCE_DIGEST")
    if not expected_image_id and not expected_digest:
        return

    # Check container Image ID
    if expected_image_id:
        cmd = ["docker", "inspect", "--format", "{{.Image}}", worker_container_name]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            actual_image_id = proc.stdout.strip()
            if actual_image_id != expected_image_id:
                raise RuntimeError(
                    f"FATAL IMAGE ID MISMATCH: Worker container '{worker_container_name}' is running image '{actual_image_id}', "
                    f"expected immutable image ID '{expected_image_id}'"
                )
        except Exception as exc:
            raise RuntimeError(f"FATAL: Failed to verify worker container image ID: {exc}") from exc

    # Check container provenance label
    if expected_digest:
        cmd = ["docker", "inspect", "--format", '{{index .Config.Labels "veritas.rag.source_digest"}}', worker_container_name]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            actual_digest = proc.stdout.strip()
            if actual_digest != expected_digest:
                raise RuntimeError(
                    f"FATAL IMAGE PROVENANCE MISMATCH: Worker container '{worker_container_name}' has digest '{actual_digest}', "
                    f"expected source digest '{expected_digest}'"
                )
        except Exception as exc:
            raise RuntimeError(f"FATAL: Failed to verify worker container provenance label: {exc}") from exc


# ── 3. Celery Consumer Pause & Resume Observability ──────────────────────────

CELERY_E2E_QUEUES = (
    "ingestion",
    "indexing",
    "embeddings",
    "retrieval",
    "default",
    "retention",
    "health",
)


async def pause_indexing_consumer(celery_app_instance: Any, timeout: float = 8.0) -> None:
    """Deterministically cancel the 'indexing' consumer and observe that it is removed."""
    celery_app_instance.control.cancel_consumer("indexing")
    inspector = celery_app_instance.control.inspect()
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        active_queues = inspector.active_queues() or {}
        assigned = [q["name"] for q_list in active_queues.values() for q in q_list]
        if "indexing" not in assigned:
            return
        await asyncio.sleep(0.15)
    raise TimeoutError(f"Timed out waiting for 'indexing' queue to pause (waited {timeout}s).")


async def resume_indexing_consumer(celery_app_instance: Any, timeout: float = 8.0) -> None:
    """Deterministically resume the 'indexing' consumer and observe that it is restored."""
    celery_app_instance.control.add_consumer("indexing")
    inspector = celery_app_instance.control.inspect()
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        active_queues = inspector.active_queues() or {}
        assigned = [q["name"] for q_list in active_queues.values() for q in q_list]
        if "indexing" in assigned:
            return
        await asyncio.sleep(0.15)
    raise TimeoutError(f"Timed out waiting for 'indexing' queue to resume (waited {timeout}s).")


async def drain_celery_queues_and_verify_quiescence(
    celery_app_instance: Any,
    redis_url: str,
    timeout: float = 15.0,
) -> None:
    """Verify that all 7 queues and workers are fully drained before any resource teardown.

    Fails closed if tasks are still active, reserved, or broker queues are not empty.
    Never uses queue purging as a substitute for legitimate draining.
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(redis_url, socket_timeout=5.0, socket_connect_timeout=5.0)
    start_time = time.monotonic()

    try:
        while time.monotonic() - start_time < timeout:
            broker_clean = True
            for q in CELERY_E2E_QUEUES:
                for attempt in range(3):
                    try:
                        llen = await r.llen(q)
                        break
                    except (aioredis.TimeoutError, aioredis.ConnectionError, OSError):
                        if attempt == 2:
                            raise
                        await asyncio.sleep(0.25)

                if llen > 0:
                    broker_clean = False
                    break

            if broker_clean:
                # Check worker in-memory and in-flight tasks
                inspector = celery_app_instance.control.inspect(timeout=2.0)
                active = (inspector.active() if inspector else None) or {}
                reserved = (inspector.reserved() if inspector else None) or {}
                scheduled = (inspector.scheduled() if inspector else None) or {}

                active_count = sum(len(tasks) for tasks in active.values())
                reserved_count = sum(len(tasks) for tasks in reserved.values())
                scheduled_count = sum(len(tasks) for tasks in scheduled.values())

                if active_count == 0 and reserved_count == 0 and scheduled_count == 0:
                    return

            await asyncio.sleep(0.5)

        raise RuntimeError(
            f"FATAL: Celery worker quiescence could not be established within {timeout}s. "
            f"Active, reserved, or broker messages remain outstanding. Cleanup BLOCKED to prevent corrupting state."
        )
    finally:
        await r.aclose()


def stop_worker_container(worker_container_name: str, timeout: int = 15) -> None:
    """Gracefully stop worker container via docker stop and verify exited status."""
    cmd_stop = ["docker", "stop", "-t", str(timeout), worker_container_name]
    subprocess.run(cmd_stop, capture_output=True, text=True, check=True, timeout=timeout + 5)

    cmd_check = ["docker", "inspect", "-f", "{{.State.Running}}", worker_container_name]
    proc = subprocess.run(cmd_check, capture_output=True, text=True, check=True, timeout=10)
    if proc.stdout.strip().lower() != "false":
        raise RuntimeError(f"FATAL: Worker container '{worker_container_name}' failed to stop cleanly.")


# ── 4. Verifiable Cleanup Implementation ──────────────────────────────────────

async def cleanup_tenant_database_records(session: AsyncSession, tenant_id: str) -> None:
    """Clean up tenant records according to the exact schema and foreign key contract.

    Verifies deletion independently across tables and raises an exception on any failure.
    """
    import re
    is_e2e_tenant = bool(re.match(r"^tenant_[ab]_e2e_\d+_[0-9a-fA-F]+$", tenant_id))
    is_uuid = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", tenant_id))
    if not (is_e2e_tenant or is_uuid):
        raise RuntimeError(f"FATAL SAFETY VIOLATION: Refusing database deletion for non-E2E tenant ID: '{tenant_id}'")


    # 1. Identify storage_objects referenced by this tenant's document versions
    res = await session.execute(
        text("""
            SELECT DISTINCT v.storage_object_id
            FROM document_versions v
            JOIN documents d ON d.id = v.document_id
            WHERE d.tenant_id = :tenant_id AND v.storage_object_id IS NOT NULL
        """),
        {"tenant_id": tenant_id},
    )
    storage_obj_ids = [row[0] for row in res.fetchall() if row[0] is not None]

    # 2. Delete documents (cascades to document_versions, chunks, embeddings, processing_jobs)
    await session.execute(
        text("DELETE FROM documents WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )

    # 3. Purge storage_objects that are no longer referenced by any remaining document version
    if storage_obj_ids:
        await session.execute(
            text("""
                DELETE FROM storage_objects
                WHERE id = ANY(:ids)
                  AND NOT EXISTS (
                      SELECT 1 FROM document_versions
                      WHERE storage_object_id = storage_objects.id
                  )
            """),
            {"ids": storage_obj_ids},
        )

    # 4. Clean up tenant diagnostics, vector metadata, and bulk batches
    await session.execute(
        text("DELETE FROM vector_index_metadata WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    await session.execute(
        text("DELETE FROM failed_job_diagnostics WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    await session.execute(
        text("DELETE FROM bulk_batches WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    await session.commit()

    # Explicit verification of database cleanup across tables
    checks = {
        "documents": "SELECT COUNT(*) FROM documents WHERE tenant_id = :tenant_id",
        "document_chunks": "SELECT COUNT(*) FROM document_chunks WHERE tenant_id = :tenant_id",
        "document_versions": """
            SELECT COUNT(*) FROM document_versions v
            JOIN documents d ON d.id = v.document_id
            WHERE d.tenant_id = :tenant_id
        """,
        "vector_index_metadata": "SELECT COUNT(*) FROM vector_index_metadata WHERE tenant_id = :tenant_id",
    }
    for table_name, query_str in checks.items():
        check_res = await session.execute(text(query_str), {"tenant_id": tenant_id})
        count = check_res.scalar()
        if count != 0:
            raise RuntimeError(
                f"Database cleanup verification failed: {count} rows remain in '{table_name}' for tenant '{tenant_id}'."
            )


async def cleanup_run_qdrant_collections(client: AsyncQdrantClient, run_id: str) -> None:
    """Enumerate and delete all Qdrant collections belonging strictly to the current run.

    Fails closed if any collection belonging to this run fails deletion or remains present.
    """
    import re
    if not re.match(r"^e2e_\d+_[0-9a-fA-F]+$", run_id):
        raise RuntimeError(f"FATAL SAFETY VIOLATION: Refusing Qdrant deletion for non-E2E run ID: '{run_id}'")

    prefix = f"raguard_e2e_{run_id}"
    response = await client.get_collections()
    matching_collections = [c.name for c in response.collections if c.name.startswith(prefix)]

    for col in matching_collections:
        try:
            await client.delete_collection(col)
        except Exception as exc:
            raise RuntimeError(f"Failed to delete Qdrant collection '{col}': {exc}") from exc

    # Verify removal without exception suppression
    post_check = await client.get_collections()
    remaining = [c.name for c in post_check.collections if c.name.startswith(prefix)]
    if remaining:
        raise RuntimeError(f"Qdrant cleanup verification failed: collections {remaining} still exist after cleanup.")


def cleanup_tenant_storage_artifacts(storage_root: Path, tenant_id: str) -> None:
    """Purge only the run-specific tenant directory and verify its removal."""
    import re
    is_e2e_tenant = bool(re.match(r"^tenant_[ab]_e2e_\d+_[0-9a-fA-F]+$", tenant_id))
    is_uuid = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", tenant_id))
    if not (is_e2e_tenant or is_uuid):
        raise RuntimeError(f"FATAL SAFETY VIOLATION: Refusing storage deletion for non-E2E tenant ID: '{tenant_id}'")

    tenant_dir = storage_root / "documents" / tenant_id
    if tenant_dir.exists() and tenant_dir.is_dir():
        shutil.rmtree(tenant_dir, ignore_errors=False)

    if tenant_dir.exists():
        raise RuntimeError(f"Storage cleanup verification failed: directory '{tenant_dir}' still exists.")


# ── 5. Pytest Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def e2e_run_id() -> str:
    return RUN_ID


@pytest.fixture(scope="session")
def e2e_storage_root() -> Path:
    return E2E_STORAGE_HOST_DIR


@pytest.fixture(scope="session")
def e2e_tenant_a(e2e_run_id: str) -> str:
    return f"tenant_a_{e2e_run_id}"


@pytest.fixture(scope="session")
def e2e_tenant_b(e2e_run_id: str) -> str:
    return f"tenant_b_{e2e_run_id}"


@pytest_asyncio.fixture
async def e2e_db_engine(e2e_run_id: str):
    """Database engine verified with cluster identifier and sentinel against raguard_test_db."""
    postgres_container = f"raguard-e2e-postgres-{e2e_run_id}"
    engine = create_async_engine(E2E_DB_URL, echo=False)
    await initialize_and_verify_database_sentinel(engine, postgres_container, e2e_run_id)
    yield engine
    await engine.dispose()


@pytest.fixture
def e2e_session_factory(e2e_db_engine) -> async_sessionmaker[AsyncSession]:
    """Provide session factory for fresh sessions during polling."""
    return async_sessionmaker(
        bind=e2e_db_engine, expire_on_commit=False, class_=AsyncSession
    )


@pytest_asyncio.fixture
async def e2e_session(e2e_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession bound to the isolated E2E test database."""
    async with e2e_session_factory() as session:
        yield session


@pytest.fixture(scope="session")
def e2e_celery_app():
    """Return the canonical application Celery singleton updated for E2E broker."""
    celery_app.conf.update(
        broker_url=E2E_CELERY_BROKER,
        result_backend=E2E_CELERY_BACKEND,
    )
    return celery_app


@pytest_asyncio.fixture
async def e2e_qdrant_client() -> AsyncGenerator[AsyncQdrantClient, None]:
    """Provide an AsyncQdrantClient bound strictly to the isolated Qdrant container."""
    client = AsyncQdrantClient(url=f"http://localhost:{E2E_QDRANT_PORT}")
    yield client
    await client.close()


@pytest_asyncio.fixture
async def e2e_preflight_verified(
    e2e_db_engine: Any,
    e2e_run_id: str,
    e2e_celery_app: Any,
) -> None:
    """Mandatory preflight fixture. Must be required by every lifecycle test."""
    postgres_container = f"raguard-e2e-postgres-{e2e_run_id}"
    cluster_id = await initialize_and_verify_database_sentinel(e2e_db_engine, postgres_container, e2e_run_id)
    await verify_schema_readiness(e2e_db_engine)
    worker_container = f"raguard-e2e-worker-{e2e_run_id}"
    verify_worker_provenance(worker_container)
    verify_worker_database_identity(worker_container, cluster_id, e2e_run_id)
    verify_worker_live(e2e_celery_app)


def verify_api_provenance(api_container_name: str) -> None:
    """Verify that the API container is running the expected immutable image ID and provenance digest."""
    expected_image_id = os.environ.get("E2E_WORKER_IMAGE_ID")
    expected_digest = os.environ.get("E2E_SOURCE_DIGEST")
    if not expected_image_id and not expected_digest:
        return

    if expected_image_id:
        cmd = ["docker", "inspect", "--format", "{{.Image}}", api_container_name]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            actual_image_id = proc.stdout.strip()
            if actual_image_id != expected_image_id:
                raise RuntimeError(
                    f"FATAL IMAGE ID MISMATCH: API container '{api_container_name}' is running image '{actual_image_id}', "
                    f"expected immutable image ID '{expected_image_id}'"
                )
        except Exception as exc:
            raise RuntimeError(f"FATAL: Failed to verify API container image ID: {exc}") from exc

    if expected_digest:
        cmd = ["docker", "inspect", "--format", '{{index .Config.Labels "veritas.rag.source_digest"}}', api_container_name]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            actual_digest = proc.stdout.strip()
            if actual_digest != expected_digest:
                raise RuntimeError(
                    f"FATAL IMAGE PROVENANCE MISMATCH: API container '{api_container_name}' has digest '{actual_digest}', "
                    f"expected source digest '{expected_digest}'"
                )
        except Exception as exc:
            raise RuntimeError(f"FATAL: Failed to verify API container provenance label: {exc}") from exc


def verify_api_live(api_base_url: str, timeout: float = 30.0) -> None:
    """Verify that the isolated FastAPI HTTP server is responsive on its dedicated port."""
    start = time.perf_counter()
    last_err = None
    while time.perf_counter() - start < timeout:
        try:
            resp = httpx.get(f"{api_base_url}/health", timeout=3.0)
            if resp.status_code == 200:
                return
        except Exception as exc:
            last_err = exc
        time.sleep(1.0)
    raise RuntimeError(
        f"FATAL: Isolated API container not responsive at '{api_base_url}/health' within {timeout}s (last error: {last_err})"
    )


@pytest_asyncio.fixture
async def e2e_api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an isolated httpx.AsyncClient bound to the live API container on port 8008."""
    async with httpx.AsyncClient(base_url=E2E_API_BASE_URL, timeout=60.0) as client:
        yield client


@pytest_asyncio.fixture
async def e2e_chat_preflight_verified(
    e2e_db_engine: Any,
    e2e_run_id: str,
    e2e_celery_app: Any,
) -> None:
    """Mandatory preflight fixture for live chat E2E verification.

    Verifies database cluster identity, schema migrations, Celery worker liveness and provenance,
    and API container liveness and provenance on the dedicated isolated port.
    """
    postgres_container = f"raguard-e2e-postgres-{e2e_run_id}"
    cluster_id = await initialize_and_verify_database_sentinel(e2e_db_engine, postgres_container, e2e_run_id)
    await verify_schema_readiness(e2e_db_engine)

    worker_container = f"raguard-e2e-worker-{e2e_run_id}"
    verify_worker_provenance(worker_container)
    verify_worker_database_identity(worker_container, cluster_id, e2e_run_id)
    verify_worker_live(e2e_celery_app)

    api_container = f"raguard-e2e-api-{e2e_run_id}"
    verify_api_provenance(api_container)
    verify_api_live(E2E_API_BASE_URL)


async def cleanup_chat_e2e_records(
    session: AsyncSession,
    workspace_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
) -> None:
    """Safely purge disposable workspace, chat, and user records created during chat E2E verification."""
    ws_str_ids = [str(wid) for wid in workspace_ids]

    # 1. Delete chat sessions and cascading messages
    await session.execute(
        text("DELETE FROM chat_sessions WHERE tenant_id = ANY(:ws_ids)"),
        {"ws_ids": ws_str_ids},
    )

    # 2. Delete documents and associated chunks/versions for each workspace tenant
    for w_str in ws_str_ids:
        await cleanup_tenant_database_records(session, w_str)

    # 3. Delete workspace settings and members
    await session.execute(
        text("DELETE FROM workspace_settings WHERE workspace_id = ANY(:w_ids)"),
        {"w_ids": workspace_ids},
    )
    await session.execute(
        text("DELETE FROM workspace_members WHERE workspace_id = ANY(:w_ids)"),
        {"w_ids": workspace_ids},
    )

    # 4. Delete workspaces
    await session.execute(
        text("DELETE FROM workspaces WHERE id = ANY(:w_ids)"),
        {"w_ids": workspace_ids},
    )

    # 5. Delete users
    await session.execute(
        text("DELETE FROM users WHERE id = ANY(:u_ids)"),
        {"u_ids": user_ids},
    )
    await session.commit()

