# Root Cause Analysis: Generation Provider Error

## 1. The Symptom
After fixing the `sentence-transformers` dependency (`RET_003`), the chat stream endpoint successfully returns an HTTP `200 OK`, but the stream payload contains an error delta: `\n[Error: Generation failed due to provider error]`.

## 2. Runtime Evidence & Tracing

### Step 1: Why does it return `200 OK`?
The FastAPI endpoint `/api/v1/chat/sessions/{session_id}/stream` uses `StreamingResponse`. In FastAPI, a `StreamingResponse` sends the HTTP `200 OK` headers immediately, *before* the generator is fully consumed. This is why the client sees a successful HTTP status code even if an error occurs later during generation.

### Step 2: Where does the error delta come from?
Inside `backend/modules/generation/services/streaming_generation_service.py`, the `generate_stream()` method wraps the LLM provider call in a `try...except` block:

```python
try:
    async for chunk in self.llm_provider.stream(request):
        # ... process chunks ...
except Exception as exc:
    logger.error("LLM generation failed during stream", ...)
    yield StreamingGenerationChunkDTO(
        chunk_index=chunk_idx,
        text_delta=f"\n[Error: Generation failed due to provider error]",
        # ...
    )
```
This block catches ANY exception raised by the `LLMProviderManager.stream()` and converts it into the exact stream delta the user observed.

### Step 3: Why did `LLMProviderManager` raise an exception?
In `backend/ai/manager.py`, `LLMProviderManager.stream()` attempts to failover across multiple providers defined in the `LLM_PROVIDER_PRIORITY` environment variable (which is set to `openrouter,gemini` in `.env`).

```python
for provider_name in self.priority_list:
    try:
        async for chunk in provider.stream(request):
            yield chunk
        return
    except Exception as exc:
        errors.append({"provider": provider_name, "error": str(exc)})

raise LLMProviderException(
    message=f"All configured LLM providers failed for streaming: {errors}",
    ...
)
```

By running a direct isolation test on the backend (`test_generation_direct.py`), the following runtime provider errors were captured:

1. **Gemini Fallback Failure:**
When OpenRouter fails, it falls back to Gemini. The test proved that the provided `GEMINI_API_KEY` is hitting a hard rate limit/quota issue:
```text
Gemini streaming error: 429 You exceeded your current quota, please check your plan and billing details. ... Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
```

2. **OpenRouter Primary Failure:**
OpenRouter itself has a model-level failover loop (`deepseek/deepseek-chat` -> `qwen/qwen-2.5-72b-instruct` -> etc.). If OpenRouter encounters an API issue (e.g., `402 Payment Required`, `429 Rate Limit`, or temporary upstream provider outages like DeepSeek's `502 Bad Gateway`), it cycles through all its models. Once all models fail, it raises an exception to the Manager. 

Because OpenRouter exhausted its failover options, and Gemini is completely out of free-tier quota, the `LLMProviderManager` throws an `LLMProviderException`, which the Generation Service catches and transforms into the `[Error: Generation failed due to provider error]` delta.

## 3. Conclusion
The original source of the error is **Provider API Quota / Connectivity Exhaustion**. The application's failover architecture correctly handled the failures (OpenRouter Models -> Gemini) but was unable to find a working provider because:
1. OpenRouter experienced a transient API/model error during the user's run.
2. The fallback Gemini API key has exceeded its free-tier quotas (`429 You exceeded your current quota`).

## 4. Next Steps
To resolve this, the backend requires either:
- Refreshing the Gemini API key to one with available quota.
- Ensuring the OpenRouter API key has sufficient credits and its upstream models are online.
- Adding a more descriptive error message to the frontend when `LLMProviderException` occurs so it doesn't just say a generic "provider error".
