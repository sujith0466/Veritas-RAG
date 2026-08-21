# Veritas RAG — LLM Provider Manager

**Version:** 1.0.0 — Production Baseline
**Module:** `backend/ai/`
**Date:** 2026-07-21

---

## Overview

The LLM Provider Manager is a production-grade reliability layer that ensures Veritas RAG **never relies on a single language model provider**. It implements automatic failover across multiple providers and, within each provider, across multiple models.

The architecture is designed for extensibility — adding a new provider requires zero changes to the business logic layer.

---

## Architecture

```
Business Logic (Query Service, Confidence Engine)
    │
    │  Uses only the LLMProvider interface
    ▼
LLMProviderManager          ← backend/ai/manager.py
    │
    │  Iterates priority list
    ├── Priority 1: openrouter
    │       │  OpenRouterProvider
    │       │  backend/ai/providers/openrouter.py
    │       │
    │       │  Iterates model list
    │       ├── Model 1 (primary free model)
    │       ├── Model 2
    │       ├── Model 3
    │       ├── Model 4
    │       └── Model 5
    │
    └── Priority 2: gemini               ← Provider-level fallback
            │  GeminiProvider
            │  backend/ai/providers/gemini.py
            │
            ├── Primary: gemini-1.5-pro
            └── Lite:    gemini-1.5-flash (for classification tasks)
```

**Graceful Terminal State:** If all providers fail → `LLMProviderException` → structured error response to user

---

## Components

### `LLMProviderManager` (`manager.py`)

The orchestration layer. Implements the `LLMProvider` interface and handles **inter-provider failover**.

```python
class LLMProviderManager(LLMProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]
    async def health_check(self) -> bool
    async def detailed_health_check(self) -> dict[str, bool]
```

**Priority List Source:** `settings.ai.priority_list` (env: `LLM_PROVIDER_PRIORITY`)

**Failover Logic:**
1. For each provider in priority list:
   - Instantiate via `ProviderRegistry`
   - Attempt `generate()` or `stream()`
   - On success → return result
   - On any exception → log warning, append to error list, continue to next provider
2. If all providers fail → raise `LLMProviderException` with full error trace

**Stream Failover Constraint:** If a stream provider has already emitted tokens, failover is NOT possible (partial response). The exception is raised immediately to prevent data corruption.

---

### `OpenRouterProvider` (`providers/openrouter.py`)

Handles **intra-provider model-level failover** within OpenRouter.

```python
class OpenRouterProvider(LLMProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]
    async def health_check(self) -> bool
```

**Model List Source:**
- Standard requests: `settings.openrouter.models`
- Lite (classification) requests: `settings.openrouter.lite_models`

**Request Flow:**
```python
for model_name in models:
    try:
        response = await client.post(url, payload=build_payload(model_name))
        if response.status_code != 200:
            # Append error, try next model
            continue
        return parse_response(response)
    except Exception:
        # Network error, timeout — try next model
        continue

raise LLMProviderException("All OpenRouter models failed")
```

---

### `GeminiProvider` (`providers/gemini.py`)

Provider-level fallback using Google's Gemini SDK.

```python
class GeminiProvider(LLMProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]
    async def health_check(self) -> bool
```

**Model Selection:** Automatically uses `lite_model` when `request.use_lite_model=True`

---

### `ProviderRegistry` (`registry.py`)

A static registry that maps provider names to provider classes.

```python
class ProviderRegistry:
    @classmethod
    def get_provider(cls, name: str) -> LLMProvider

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None
```

**Registered Providers:**
| Name | Class |
|------|-------|
| `openrouter` | `OpenRouterProvider` |
| `gemini` | `GeminiProvider` |

**Adding a New Provider:**
```python
# In backend/ai/registry.py
ProviderRegistry.register("anthropic", AnthropicProvider)
```

Zero business logic changes required.

---

### `LLMProvider` Interface (`interfaces/llm_provider.py`)

All providers implement this abstract interface:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

---

## Request & Response Models

### `LLMRequest`

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | `str` | The user/system prompt |
| `system_instruction` | `str \| None` | Optional system instruction |
| `temperature` | `float \| None` | Sampling temperature (overrides default) |
| `max_output_tokens` | `int \| None` | Max tokens to generate (overrides default) |
| `use_lite_model` | `bool` | Use cheaper/faster lite model (classification tasks) |

### `LLMResponse`

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Generated text |
| `input_tokens` | `int` | Prompt token count |
| `output_tokens` | `int` | Completion token count |
| `model_used` | `str` | Name of the model that generated the response |
| `metadata` | `dict` | Provider-specific metadata |

---

## Retry & Timeout Strategy

### Timeouts (Configurable via Environment)

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| OpenRouter request timeout | `OPENROUTER_REQUEST_TIMEOUT` | 60s | Per-request timeout for non-streaming calls |
| Gemini request timeout | `GEMINI_REQUEST_TIMEOUT` | 60s | Passed via `request_options` |
| Health check timeout | (hardcoded) | 10s | Quick probe timeout |

### Retry Policy

Retries are handled by **model/provider iteration** (not traditional retry loops with delays):

| Scenario | Behavior |
|----------|---------|
| HTTP 4xx / 5xx | Skip to next model in list |
| Network timeout | Skip to next model in list |
| Connection error | Skip to next model in list |
| All models failed | Escalate to next provider |
| All providers failed | Raise `LLMProviderException` |
| Mid-stream failure | Raise immediately (no failover possible) |

This "fail-fast and escalate" approach avoids exponential delays on permanent failures (e.g., quota exhaustion) while still attempting all available options.

---

## Health Monitoring

### `health_check()` (Basic)

Returns `True` if **any** provider in the priority list is healthy.

Used by: `GET /api/v1/health/detailed`

### `detailed_health_check()` (Admin)

Returns per-provider health status:

```json
{
  "openrouter": true,
  "gemini": false
}
```

Used by: `GET /api/v1/health/detailed` (admin-only)

---

## Configuration Reference

### Environment Variables

```bash
# Provider Priority (comma-separated, in priority order)
LLM_PROVIDER_PRIORITY=openrouter,gemini

# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODELS=meta-llama/llama-3.1-8b-instruct:free,mistralai/mistral-7b-instruct:free,...
OPENROUTER_LITE_MODELS=meta-llama/llama-3.2-3b-instruct:free
OPENROUTER_TEMPERATURE=0.1
OPENROUTER_MAX_OUTPUT_TOKENS=4096
OPENROUTER_REQUEST_TIMEOUT=60

# Gemini Configuration
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-1.5-pro
GEMINI_LITE_MODEL=gemini-1.5-flash
GEMINI_TEMPERATURE=0.1
GEMINI_MAX_OUTPUT_TOKENS=4096
GEMINI_REQUEST_TIMEOUT=60
```

---

## Adding a New Provider

1. **Create provider class** in `backend/ai/providers/your_provider.py`:

```python
from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse

class AnthropicProvider(LLMProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        ...

    async def health_check(self) -> bool:
        ...
```

2. **Register in registry** (`backend/ai/registry.py`):

```python
from .providers.your_provider import AnthropicProvider
ProviderRegistry.register("anthropic", AnthropicProvider)
```

3. **Add to priority list** (`.env`):

```bash
LLM_PROVIDER_PRIORITY=openrouter,anthropic,gemini
```

4. **Add settings model** (`backend/core/config/`) — Pydantic `BaseSettings` for your provider credentials.

No changes required to business logic, query services, or the manager.

---

## Observability

All provider calls are logged with `structlog`:

```json
{
  "event": "Attempting LLM generate",
  "provider": "openrouter",
  "level": "debug"
}

{
  "event": "Provider generation failed, attempting next in priority list",
  "failed_provider": "openrouter",
  "error": "HTTP 429: Rate limit exceeded",
  "level": "warning"
}

{
  "event": "LLM generate succeeded via fallback provider",
  "successful_provider": "gemini",
  "prior_failures": 1,
  "level": "info"
}
```

Metrics that should be tracked in production monitoring:
- `llm.provider.failover_count` — frequency of failover events
- `llm.provider.success_by_provider` — which provider ultimately served each request
- `llm.request.latency_ms` — end-to-end latency per provider
- `llm.provider.health_status` — per-provider health check results

---

## Supported Future Providers

| Provider | Status | Notes |
|---------|--------|-------|
| OpenRouter (multi-model) | Production | Primary provider |
| Google Gemini | Production | Fallback provider |
| Anthropic Claude | Planned | Direct API |
| OpenAI | Planned | Direct API |
| Azure OpenAI | Planned | Enterprise deployment |
| Groq | Planned | Ultra-low latency inference |
| Ollama | Planned | Local/private models |
| Together AI | Planned | Fine-tuned model support |

---

*This document reflects the production-frozen backend baseline as of 2026-07-21.*
