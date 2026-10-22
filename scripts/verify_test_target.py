"""
Veritas-RAG — WP-TEST-B Preflight Target Verification Script.

Ensures that:
1. APP_ENVIRONMENT is set to 'testing' (and app.is_testing is True).
2. APP_SECRET_KEY is non-empty.
3. DATABASE_URL and settings.database.url point strictly to the disposable test database
   (raguard_test on localhost:5432).
4. REDIS_URL points strictly to Redis index 15 on localhost:6379.
5. MINIO_ENDPOINT points strictly to localhost:9000.
6. QDRANT_HOST / QDRANT_PORT point strictly to localhost:6333.
7. With --probe-db, performs a non-destructive live database query (SELECT current_database();)
   to prove that the connected database is strictly 'raguard_test' before migrations.
8. With --probe-redis, verifies live connectivity to Redis index 15.
9. With --probe-minio, verifies live connectivity to MinIO test health endpoint.
10. With --probe-qdrant, verifies live connectivity to Qdrant test /readyz endpoint.
11. With --probe-all, executes all live service probes (DB, Redis, MinIO, Qdrant).
12. With --init-buckets, initializes required test buckets in MinIO.

Zero secrets or credentials are leaked in logs.
"""

import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse


def mask_url(parsed):
    netloc = parsed.netloc
    if parsed.username and parsed.password:
        netloc = f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"
    elif parsed.username:
        netloc = f"{parsed.username}@{parsed.hostname}:{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def verify_environment_variables() -> None:
    app_env = os.environ.get("APP_ENVIRONMENT", "")
    if app_env not in ("testing", "test"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: APP_ENVIRONMENT must be 'testing', got '{app_env}'.\n"
        )
        sys.exit(1)
    print(f"PREFLIGHT OK: APP_ENVIRONMENT is '{app_env}'.")

    secret_key = os.environ.get("APP_SECRET_KEY", "")
    if not secret_key or len(secret_key.strip()) == 0:
        sys.stderr.write("PREFLIGHT ERROR: APP_SECRET_KEY is empty or not set.\n")
        sys.exit(1)
    print("PREFLIGHT OK: APP_SECRET_KEY is non-empty (value masked).")


def verify_database_target(db_url: str, source_label: str) -> None:
    if not db_url:
        sys.stderr.write(f"PREFLIGHT ERROR: {source_label} is empty or not set.\n")
        sys.exit(1)

    parsed = urlparse(db_url)
    if parsed.scheme != "postgresql+asyncpg":
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} scheme must be 'postgresql+asyncpg', got '{parsed.scheme}'.\n"
        )
        sys.exit(1)

    if parsed.hostname not in ("127.0.0.1", "localhost"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} hostname must be '127.0.0.1' or 'localhost', got '{parsed.hostname}'.\n"
        )
        sys.exit(1)

    if parsed.port != 5432:
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} port must be 5432, got '{parsed.port}'.\n"
        )
        sys.exit(1)

    db_name = parsed.path.lstrip("/")
    if db_name != "raguard_test":
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} database name must be strictly 'raguard_test', got '{db_name}'. Refusing target.\n"
        )
        sys.exit(1)

    print(f"PREFLIGHT OK: {source_label} verified -> {mask_url(parsed)}")


def verify_redis_target(redis_url: str, source_label: str) -> None:
    if not redis_url:
        sys.stderr.write(f"PREFLIGHT ERROR: {source_label} is empty or not set.\n")
        sys.exit(1)

    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} scheme must be 'redis', got '{parsed.scheme}'.\n"
        )
        sys.exit(1)

    if parsed.hostname not in ("127.0.0.1", "localhost"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} hostname must be '127.0.0.1' or 'localhost', got '{parsed.hostname}'.\n"
        )
        sys.exit(1)

    if parsed.port != 6379:
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} port must be 6379, got '{parsed.port}'.\n"
        )
        sys.exit(1)

    db_index = parsed.path.lstrip("/")
    if db_index != "15":
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} db index must be strictly '15', got '{db_index}'. Refusing target.\n"
        )
        sys.exit(1)

    print(f"PREFLIGHT OK: {source_label} verified -> {mask_url(parsed)}")


def verify_minio_target(minio_endpoint: str, source_label: str) -> None:
    if not minio_endpoint:
        sys.stderr.write(f"PREFLIGHT ERROR: {source_label} is empty or not set.\n")
        sys.exit(1)

    parsed = urlparse(minio_endpoint)
    if parsed.scheme not in ("http", "https"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} scheme must be http/https, got '{parsed.scheme}'.\n"
        )
        sys.exit(1)

    if parsed.hostname not in ("127.0.0.1", "localhost"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} hostname must be '127.0.0.1' or 'localhost', got '{parsed.hostname}'.\n"
        )
        sys.exit(1)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port != 9000:
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} port must be 9000, got '{port}'. Refusing target.\n"
        )
        sys.exit(1)

    print(f"PREFLIGHT OK: {source_label} verified -> {mask_url(parsed)}")


def verify_qdrant_target(qdrant_host: str, qdrant_port: int, source_label: str) -> None:
    if not qdrant_host:
        sys.stderr.write(f"PREFLIGHT ERROR: {source_label} host is empty or not set.\n")
        sys.exit(1)

    if qdrant_host not in ("127.0.0.1", "localhost"):
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} host must be '127.0.0.1' or 'localhost', got '{qdrant_host}'.\n"
        )
        sys.exit(1)

    if qdrant_port != 6333:
        sys.stderr.write(
            f"PREFLIGHT ERROR: {source_label} port must be 6333, got '{qdrant_port}'. Refusing target.\n"
        )
        sys.exit(1)

    print(f"PREFLIGHT OK: {source_label} verified -> http://{qdrant_host}:{qdrant_port}")


async def probe_postgres_live(db_url: str) -> None:
    """Non-destructive probe verifying current_database() == 'raguard_test' without leaking credentials."""
    import asyncpg

    parsed = urlparse(db_url)
    try:
        conn = await asyncpg.connect(
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            timeout=5.0,
        )
        try:
            current_db = await conn.fetchval("SELECT current_database();")
            if current_db != "raguard_test":
                sys.stderr.write(
                    f"PREFLIGHT DB PROBE FAILED: current_database() is '{current_db}', expected 'raguard_test'. Refusing target.\n"
                )
                sys.exit(1)
            print(f"PREFLIGHT OK: Live DB identity probe confirmed current_database() == '{current_db}'")
        finally:
            await conn.close()
    except Exception as e:
        sys.stderr.write(f"PREFLIGHT DB PROBE ERROR: Failed to connect or query database: {e}\n")
        sys.exit(1)


async def probe_redis_live(redis_url: str) -> None:
    """Non-destructive probe verifying Redis connectivity and DB index 15 without leaking credentials."""
    import redis.asyncio as aioredis

    parsed = urlparse(redis_url)
    db_index = parsed.path.lstrip("/")
    try:
        client = aioredis.from_url(redis_url, socket_timeout=5.0)
        try:
            pong = await client.ping()
            if not pong:
                sys.stderr.write("PREFLIGHT REDIS PROBE FAILED: Redis PING did not return True.\n")
                sys.exit(1)
            print(f"PREFLIGHT OK: Live Redis probe confirmed PING on DB index {db_index}.")
        finally:
            await client.aclose()
    except Exception as e:
        sys.stderr.write(f"PREFLIGHT REDIS PROBE ERROR: Failed to connect or PING Redis: {e}\n")
        sys.exit(1)


async def probe_minio_live(minio_endpoint: str) -> None:
    """Non-destructive probe verifying MinIO live health endpoint responds 200."""
    import httpx

    health_url = f"{minio_endpoint.rstrip('/')}/minio/health/live"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
            if resp.status_code != 200:
                sys.stderr.write(
                    f"PREFLIGHT MINIO PROBE FAILED: {health_url} returned HTTP {resp.status_code}.\n"
                )
                sys.exit(1)
            print("PREFLIGHT OK: Live MinIO health probe confirmed HTTP 200.")
    except Exception as e:
        sys.stderr.write(f"PREFLIGHT MINIO PROBE ERROR: Failed to reach MinIO health endpoint: {e}\n")
        sys.exit(1)


async def probe_qdrant_live(qdrant_host: str, qdrant_port: int) -> None:
    """Non-destructive probe verifying Qdrant /readyz endpoint responds 200."""
    import httpx

    ready_url = f"http://{qdrant_host}:{qdrant_port}/readyz"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(ready_url)
            if resp.status_code != 200:
                sys.stderr.write(
                    f"PREFLIGHT QDRANT PROBE FAILED: {ready_url} returned HTTP {resp.status_code}.\n"
                )
                sys.exit(1)
            print("PREFLIGHT OK: Live Qdrant /readyz probe confirmed HTTP 200.")
    except Exception as e:
        sys.stderr.write(f"PREFLIGHT QDRANT PROBE ERROR: Failed to reach Qdrant /readyz: {e}\n")
        sys.exit(1)


def sign_s3_request(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: bytes,
    access_key: str,
    secret_key: str,
    region: str = "us-east-1",
    service: str = "s3",
) -> dict[str, str]:
    """Sign an S3 HTTP request using AWS Signature Version 4."""
    from datetime import datetime, timezone
    import hashlib
    import hmac
    from urllib.parse import parse_qsl, quote, urlparse

    parsed = urlparse(url)
    host = parsed.netloc

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(payload).hexdigest()

    req_headers = {k.lower(): v.strip() for k, v in headers.items()}
    req_headers["host"] = host
    req_headers["x-amz-date"] = amz_date
    req_headers["x-amz-content-sha256"] = payload_hash

    # Sorted header keys
    sorted_header_keys = sorted(req_headers.keys())
    canonical_headers = "".join(f"{k}:{req_headers[k]}\n" for k in sorted_header_keys)
    signed_headers = ";".join(sorted_header_keys)

    # Canonical query string
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    sorted_params = sorted(query_params, key=lambda x: x[0])
    canonical_query = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" if v else f"{quote(k, safe='-_.~')}="
        for k, v in sorted_params
    )

    canonical_path = quote(parsed.path or "/", safe="/-_.~")

    canonical_request = (
        f"{method}\n"
        f"{canonical_path}\n"
        f"{canonical_query}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashed_canonical}"

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_secret = ("AWS4" + secret_key).encode("utf-8")
    k_date = _sign(k_secret, date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")

    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    out_headers = dict(req_headers)
    out_headers["authorization"] = auth_header
    return out_headers


async def init_buckets_live(minio_endpoint: str) -> None:
    """Idempotently initialize required MinIO test buckets with versioning and WORM governance policies."""
    import httpx

    # Resolve bucket names from central BucketNameBuilder
    from backend.document.storage.utils import BucketNameBuilder

    doc_bucket = BucketNameBuilder.build_document_bucket()
    audit_bucket = BucketNameBuilder.build_audit_bucket()

    access_key = os.environ.get("MINIO_ACCESS_KEY", "minio_test_user")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minio_test_password_only")
    endpoint = minio_endpoint.rstrip("/")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Helper: Ensure bucket creation
        async def _ensure_bucket(bucket_name: str, object_lock_enabled: bool) -> None:
            url = f"{endpoint}/{bucket_name}"
            headers = {}
            if object_lock_enabled:
                headers["x-amz-bucket-object-lock-enabled"] = "true"
            signed_headers = sign_s3_request(
                method="PUT",
                url=url,
                headers=headers,
                payload=b"",
                access_key=access_key,
                secret_key=secret_key,
            )
            resp = await client.put(url, headers=signed_headers)
            if resp.status_code == 200:
                print(f"PREFLIGHT OK: Created MinIO bucket '{bucket_name}' (object_lock={object_lock_enabled}).")
            elif resp.status_code == 409 or "BucketAlreadyOwnedByYou" in resp.text or "BucketAlreadyExists" in resp.text:
                print(f"PREFLIGHT OK: MinIO bucket '{bucket_name}' already exists (idempotent).")
            else:
                sys.stderr.write(
                    f"PREFLIGHT MINIO INIT ERROR: Failed to create bucket '{bucket_name}': HTTP {resp.status_code} {resp.text}\n"
                )
                sys.exit(1)

        # 2. Helper: Enable versioning
        async def _enable_versioning(bucket_name: str) -> None:
            url = f"{endpoint}/{bucket_name}?versioning="
            xml_payload = (
                b'<VersioningConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<Status>Enabled</Status>"
                b"</VersioningConfiguration>"
            )
            headers = {"content-type": "application/xml"}
            signed_headers = sign_s3_request(
                method="PUT",
                url=url,
                headers=headers,
                payload=xml_payload,
                access_key=access_key,
                secret_key=secret_key,
            )
            resp = await client.put(url, headers=signed_headers, content=xml_payload)
            if resp.status_code == 200:
                print(f"PREFLIGHT OK: Versioning enabled on MinIO bucket '{bucket_name}'.")
            else:
                sys.stderr.write(
                    f"PREFLIGHT MINIO INIT ERROR: Failed to enable versioning on '{bucket_name}': HTTP {resp.status_code} {resp.text}\n"
                )
                sys.exit(1)

        # 3. Helper: Apply WORM Object Lock policy (Governance mode, 7 years)
        async def _apply_worm_policy(bucket_name: str) -> None:
            url = f"{endpoint}/{bucket_name}?object-lock="
            xml_payload = (
                b'<ObjectLockConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule>"
                b"<DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"<Years>7</Years>"
                b"</DefaultRetention>"
                b"</Rule>"
                b"</ObjectLockConfiguration>"
            )
            headers = {"content-type": "application/xml"}
            signed_headers = sign_s3_request(
                method="PUT",
                url=url,
                headers=headers,
                payload=xml_payload,
                access_key=access_key,
                secret_key=secret_key,
            )
            resp = await client.put(url, headers=signed_headers, content=xml_payload)
            if resp.status_code == 200:
                print(f"PREFLIGHT OK: WORM Object Lock Governance policy (7 years) applied on MinIO bucket '{bucket_name}'.")
            else:
                sys.stderr.write(
                    f"PREFLIGHT MINIO INIT ERROR: Failed to apply WORM policy on '{bucket_name}': HTTP {resp.status_code} {resp.text}\n"
                )
                sys.exit(1)

        # Execute Document Bucket (Versioning Only)
        await _ensure_bucket(doc_bucket, object_lock_enabled=False)
        await _enable_versioning(doc_bucket)

        # Execute Audit Bucket (Versioning + WORM Object Lock)
        await _ensure_bucket(audit_bucket, object_lock_enabled=True)
        await _enable_versioning(audit_bucket)
        await _apply_worm_policy(audit_bucket)

    print("PREFLIGHT OK: Live MinIO test buckets verified/initialized with versioning and WORM governance.")


def main():
    parser = argparse.ArgumentParser(description="Veritas-RAG Test Target Preflight")
    parser.add_argument(
        "--probe-db",
        action="store_true",
        help="Perform non-destructive live probe verifying current_database() == 'raguard_test'",
    )
    parser.add_argument(
        "--probe-redis",
        action="store_true",
        help="Perform non-destructive live probe verifying Redis index 15 connectivity",
    )
    parser.add_argument(
        "--probe-minio",
        action="store_true",
        help="Perform non-destructive live probe to MinIO health endpoint",
    )
    parser.add_argument(
        "--probe-qdrant",
        action="store_true",
        help="Perform non-destructive live probe to Qdrant /readyz endpoint",
    )
    parser.add_argument(
        "--probe-all",
        action="store_true",
        help="Perform non-destructive live probes to DB, Redis, MinIO, and Qdrant",
    )
    parser.add_argument(
        "--init-buckets",
        action="store_true",
        help="Idempotently initialize MinIO test buckets",
    )
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    verify_environment_variables()

    env_db = os.environ.get("DATABASE_URL", "")
    verify_database_target(env_db, "Environment DATABASE_URL")

    # Verify effective settings as evaluated by Pydantic / Alembic
    try:
        from backend.core.config import get_settings
        settings = get_settings()
        if not settings.is_testing:
            sys.stderr.write("PREFLIGHT ERROR: settings.is_testing evaluated to False.\n")
            sys.exit(1)
        print("PREFLIGHT OK: settings.is_testing is True.")

        settings_db = str(settings.database.url)
        verify_database_target(settings_db, "Settings get_settings().database.url (Alembic target)")
    except Exception as e:
        sys.stderr.write(f"PREFLIGHT ERROR: Could not import or evaluate get_settings(): {e}\n")
        sys.exit(1)

    env_redis = os.environ.get("REDIS_URL", "")
    verify_redis_target(env_redis, "Environment REDIS_URL")

    env_minio = os.environ.get("MINIO_ENDPOINT", "http://127.0.0.1:9000")
    verify_minio_target(env_minio, "Environment MINIO_ENDPOINT")

    env_qdrant_host = os.environ.get("QDRANT_HOST", "127.0.0.1")
    env_qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
    verify_qdrant_target(env_qdrant_host, env_qdrant_port, "Environment Qdrant")

    if args.probe_all or args.probe_db:
        asyncio.run(probe_postgres_live(env_db))

    if args.probe_all or args.probe_redis:
        asyncio.run(probe_redis_live(env_redis))

    if args.probe_all or args.probe_minio:
        asyncio.run(probe_minio_live(env_minio))

    if args.probe_all or args.probe_qdrant:
        asyncio.run(probe_qdrant_live(env_qdrant_host, env_qdrant_port))

    if args.init_buckets:
        asyncio.run(init_buckets_live(env_minio))

    print("PREFLIGHT ALL CHECKS PASSED: Target is isolated disposable test infrastructure.")


if __name__ == "__main__":
    main()
