import asyncio
from collections.abc import AsyncGenerator
import hashlib
import hmac
import ssl
import time
import uuid

import httpx
import structlog

from backend.ai.providers.v1_engine.exceptions import (
    V1AuthenticationError,
    V1EngineStreamAbortError,
    V1EngineUnavailableError,
    V1EngineVersionMismatchError,
    V1TLSError,
)
from backend.ai.schemas.wrapper_dto import AIWrapperRequest, V1EngineStreamChunk
from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException
from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.circuit_breaker.states import CircuitState

logger = structlog.get_logger(__name__)


class V1EngineClient:
    """Production-hardened HTTP client for the V1 AI Engine."""

    _client: httpx.AsyncClient | None = None
    _negotiated_version: str | None = None

    @classmethod
    async def initialize(cls) -> None:
        """Initialize the connection pool, mTLS context, and negotiate version."""
        settings = get_settings().v1_engine
        if not settings.enabled:
            logger.info("V1 Engine is disabled via configuration.")
            return

        if not settings.base_url:
            raise ValueError("V1_ENGINE_BASE_URL is required when enabled.")

        # Build SSL Context
        try:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            if settings.ca_cert_path:
                ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
            if settings.client_cert_path and settings.client_key_path:
                ssl_context.load_cert_chain(
                    certfile=settings.client_cert_path,
                    keyfile=settings.client_key_path
                )
        except Exception as e:
            logger.critical("Failed to build V1 Engine SSL context", error=str(e))
            raise V1TLSError() from e

        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive,
            keepalive_expiry=60.0
        )
        timeout = httpx.Timeout(
            connect=settings.connect_timeout,
            read=settings.per_attempt_timeout,
            write=settings.per_attempt_timeout,
            pool=settings.connect_timeout
        )

        cls._client = httpx.AsyncClient(
            base_url=settings.base_url,
            verify=ssl_context,
            limits=limits,
            timeout=timeout,
            http2=True,
        )

        # Version Negotiation
        try:
            res = await cls._client.get("/v1/version")
            res.raise_for_status()
            data = res.json()
            cls._negotiated_version = data.get("version")
            capabilities = data.get("capabilities", [])

            if "streaming" not in capabilities or "mTLS" not in capabilities:
                raise V1EngineVersionMismatchError("Required capabilities 'streaming' or 'mTLS' missing.")

            logger.info("V1 Engine Client initialized", version=cls._negotiated_version)
        except httpx.HTTPError as e:
            logger.critical("V1 Engine version negotiation failed", error=str(e))
            await cls.close()
            raise V1EngineVersionMismatchError() from e

    @classmethod
    async def close(cls) -> None:
        if cls._client:
            await cls._client.aclose()
            cls._client = None
            logger.info("V1 Engine Client closed.")

    @classmethod
    def _sign_request(cls, method: str, path: str, body_bytes: bytes, timestamp: int) -> str:
        settings = get_settings().v1_engine
        if not settings.signing_key:
            return ""

        body_hash = hashlib.sha256(body_bytes).hexdigest() if body_bytes else ""
        payload = f"{method}\n{path}\n{timestamp}\n{body_hash}"

        signature = hmac.new(
            settings.signing_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    @classmethod
    async def stream(
        cls, request: AIWrapperRequest, correlation_id: str
    ) -> AsyncGenerator[V1EngineStreamChunk, None]:
        """Stream SSE generation from V1 Engine."""
        settings = get_settings().v1_engine
        if not settings.enabled or not cls._client:
            raise V1EngineUnavailableError("V1 Engine is not enabled or initialized.")

        cb_engine = CircuitBreakerEngine()
        tenant_str = str(request.tenant_id)

        # 1. Circuit Breaker Check
        cb_state = await cb_engine.check_state(tenant_str, "v1_engine")
        if cb_state == CircuitState.OPEN:
            raise LLMProviderException("Circuit Breaker OPEN for V1 Engine", status_code=503)

        # 2. Build Request
        path = "/v1/generate/stream"
        payload_json = request.model_dump(mode="json")
        body_bytes = request.model_dump_json().encode("utf-8")

        ts = int(time.time())
        signature = cls._sign_request("POST", path, body_bytes, ts)

        headers = {
            "X-Tenant-ID": tenant_str,
            "X-Workspace-ID": str(request.workspace_id),
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": str(uuid.uuid4()),
            "X-Request-Timestamp": str(ts),
            "X-Request-Signature": f"HMAC-SHA256={signature}",
            "X-Client-Version": "raguard-v2/1.0",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if settings.service_token:
            headers["Authorization"] = f"Bearer {settings.service_token}"

        max_attempts = 4
        base_delay = 0.5

        for attempt in range(max_attempts):
            chunks_yielded = 0
            try:
                # httpx stream
                async with cls._client.stream("POST", path, headers=headers, content=body_bytes) as response:
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "2"))
                        await cb_engine.record_failure(tenant_str, "v1_engine", "429")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        raise V1EngineUnavailableError("Rate limited.")

                    if response.status_code in (401, 403):
                        await cb_engine.record_failure(tenant_str, "v1_engine", str(response.status_code))
                        raise V1AuthenticationError()

                    if response.status_code >= 500:
                        await cb_engine.record_failure(tenant_str, "v1_engine", str(response.status_code))
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(base_delay * (2 ** attempt))
                            continue
                        raise V1EngineUnavailableError(f"Server error {response.status_code}")

                    response.raise_for_status()
                    await cb_engine.record_success(tenant_str, "v1_engine")

                    # SSE Parsing with backpressure
                    queue = asyncio.Queue(maxsize=100)

                    async def _producer():
                        try:
                            iterator = response.aiter_lines().__aiter__()
                            is_first = True
                            while True:
                                try:
                                    # Strict TTFT (10s) vs Inter-token (15s)
                                    timeout_val = 10.0 if is_first else 15.0
                                    line = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_val)
                                except asyncio.TimeoutError:
                                    if is_first:
                                        logger.error("V1 stream TTFT timeout (10s exceeded)")
                                        await queue.put(V1EngineUnavailableError("TTFT Timeout"))
                                    else:
                                        logger.error("V1 stream inter-token timeout (15s exceeded)")
                                        await queue.put(V1EngineStreamAbortError("Inter-token timeout"))
                                    break
                                except StopAsyncIteration:
                                    break

                                is_first = False

                                if not line:
                                    continue
                                if line.startswith("data: "):
                                    raw = line[6:].strip()
                                    if raw == "[DONE]":
                                        break
                                    if '"type": "heartbeat"' in raw:
                                        continue

                                    try:
                                        chunk = V1EngineStreamChunk.model_validate_json(raw)
                                        await queue.put(chunk)
                                    except Exception as e:
                                        logger.warning("Failed to parse V1 chunk", error=str(e))
                        except asyncio.CancelledError:
                            await response.aclose()
                            raise
                        except Exception as e:
                            logger.error("V1 stream read error", error=str(e))
                            await queue.put(e)
                        finally:
                            await queue.put(None) # EOF marker

                    producer_task = asyncio.create_task(_producer())

                    try:
                        while True:
                            item = await queue.get()
                            if item is None:
                                break
                            if isinstance(item, Exception):
                                if chunks_yielded == 0:
                                    raise item  # Retryable
                                else:
                                    raise V1EngineStreamAbortError() from item

                            chunks_yielded += 1
                            yield item
                            queue.task_done()
                    finally:
                        producer_task.cancel()
                        try:
                            await producer_task
                        except asyncio.CancelledError:
                            pass

                return # Success

            except httpx.ConnectError as e:
                await cb_engine.record_failure(tenant_str, "v1_engine", "connect_error")
                if chunks_yielded > 0:
                    raise V1EngineStreamAbortError() from e
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise V1EngineUnavailableError() from e
            except httpx.TimeoutException as e:
                await cb_engine.record_failure(tenant_str, "v1_engine", "timeout")
                if chunks_yielded > 0:
                    raise V1EngineStreamAbortError() from e
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise V1EngineUnavailableError() from e
            except V1EngineStreamAbortError:
                raise
            except Exception as e:
                if chunks_yielded > 0:
                    raise V1EngineStreamAbortError() from e
                raise

        raise V1EngineUnavailableError("Max retries exceeded.")
