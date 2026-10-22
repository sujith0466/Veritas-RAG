"""Model Pricing and Financial Accounting Service — WP-3B.

Maintains versioned model pricing tables (prompt and completion rates per 1M tokens)
and computes financial liabilities for token consumption across providers.
Strictly distinguishes PRICED vs UNPRICED model usage.
"""
from dataclasses import dataclass
import re
from typing import Any

from structlog import get_logger

from backend.modules.analytics.schemas.errors import InvalidPricingModelError

logger = get_logger(__name__)


@dataclass
class CostCalculationResult:
    """Detailed financial accounting result for token consumption."""

    total_cost_usd: float
    cost_status: str  # "PRICED" | "UNPRICED"
    prompt_rate_per_1m: float | None = None
    completion_rate_per_1m: float | None = None
    model_name: str = ""
    provider: str = ""
    pricing_version: str = "2026-10-v1"
    is_zero_cost: bool = False


class ModelPricingService:
    """Versioned model pricing table providing deterministic financial rates."""

    VERSION = "2026-10-v1"

    # Static pricing table: prompt and completion rates in USD per 1,000,000 tokens
    DEFAULT_RATES_PER_1M: dict[str, dict[str, float]] = {
        # OpenAI LLM
        "gpt-4o": {"prompt": 5.00, "completion": 15.00},
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
        "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
        "gpt-4": {"prompt": 30.00, "completion": 60.00},
        "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
        # OpenAI Embeddings
        "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
        "text-embedding-3-large": {"prompt": 0.13, "completion": 0.0},
        "text-embedding-ada-002": {"prompt": 0.10, "completion": 0.0},
        # Anthropic
        "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
        "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
        "anthropic-claude-3-opus": {"prompt": 15.00, "completion": 75.00},
        "claude-3-sonnet": {"prompt": 3.00, "completion": 15.00},
        "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
        # Google Gemini
        "gemini-1.5-pro": {"prompt": 3.50, "completion": 10.50},
        "gemini-1.5-flash": {"prompt": 0.35, "completion": 1.05},
        "gemini-1.0-pro": {"prompt": 0.50, "completion": 1.50},
        # Cohere
        "command-r-plus": {"prompt": 3.00, "completion": 15.00},
        "command-r": {"prompt": 0.50, "completion": 1.50},
        "embed-english-v3.0": {"prompt": 0.10, "completion": 0.0},
        "embed-multilingual-v3.0": {"prompt": 0.10, "completion": 0.0},
        # Legitimate Zero-Cost Models (local offline embeddings / self-hosted models / test mocks)
        "local": {"prompt": 0.0, "completion": 0.0},
        "local-model": {"prompt": 0.0, "completion": 0.0},
        "all-minilm-l6-v2": {"prompt": 0.0, "completion": 0.0},
        "mock-llm": {"prompt": 0.0, "completion": 0.0},
        "mock": {"prompt": 0.0, "completion": 0.0},
        "test-zero-cost": {"prompt": 0.0, "completion": 0.0},
    }

    def __init__(
        self, custom_rates: dict[str, dict[str, float]] | None = None
    ) -> None:
        self.pricing_table = dict(self.DEFAULT_RATES_PER_1M)
        if custom_rates:
            self.pricing_table.update(custom_rates)

    def _normalize_model_name(self, model_name: str | None) -> str:
        if not model_name:
            return ""
        norm = model_name.strip().lower()
        # Strip provider prefixes like 'openai/gpt-4o' -> 'gpt-4o'
        if "/" in norm:
            norm = norm.split("/")[-1]
        return norm

    def calculate_cost(
        self,
        provider: str | None,
        model_name: str | None,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> CostCalculationResult:
        """Calculate dynamic financial cost from token counts.

        Returns CostCalculationResult with cost_status='PRICED' for known models,
        or cost_status='UNPRICED' for unconfigured/unknown models.
        """
        norm_model = self._normalize_model_name(model_name)
        norm_provider = (provider or "default").strip().lower()

        # Handle negative tokens safely
        safe_prompt = max(0, prompt_tokens or 0)
        safe_completion = max(0, completion_tokens or 0)

        rates = self.pricing_table.get(norm_model)
        if not rates:
            logger.warning(
                "Model pricing not found; recording usage as UNPRICED",
                model=model_name,
                provider=provider,
                normalized_model=norm_model,
            )
            return CostCalculationResult(
                total_cost_usd=0.0,
                cost_status="UNPRICED",
                prompt_rate_per_1m=None,
                completion_rate_per_1m=None,
                model_name=norm_model or str(model_name),
                provider=norm_provider,
                pricing_version=self.VERSION,
                is_zero_cost=False,
            )

        prompt_rate = rates.get("prompt", 0.0)
        completion_rate = rates.get("completion", 0.0)

        # Validate non-negative rates
        if prompt_rate < 0.0 or completion_rate < 0.0:
            logger.error("Invalid negative pricing rates configured", model=norm_model, rates=rates)
            return CostCalculationResult(
                total_cost_usd=0.0,
                cost_status="UNPRICED",
                prompt_rate_per_1m=None,
                completion_rate_per_1m=None,
                model_name=norm_model,
                provider=norm_provider,
                pricing_version=self.VERSION,
                is_zero_cost=False,
            )

        prompt_cost = (safe_prompt / 1_000_000.0) * prompt_rate
        completion_cost = (safe_completion / 1_000_000.0) * completion_rate
        total_cost = round(prompt_cost + completion_cost, 8)

        is_zero = prompt_rate == 0.0 and completion_rate == 0.0

        return CostCalculationResult(
            total_cost_usd=total_cost,
            cost_status="PRICED",
            prompt_rate_per_1m=prompt_rate,
            completion_rate_per_1m=completion_rate,
            model_name=norm_model,
            provider=norm_provider,
            pricing_version=self.VERSION,
            is_zero_cost=is_zero,
        )


class PricingEngine:
    """Legacy compatibility facade for PricingEngine."""

    def __init__(self, service: ModelPricingService | None = None) -> None:
        self.pricing_service = service or ModelPricingService()
        # Per-token rate map for backward compatibility
        self.pricing_table = {
            m: {
                "prompt": rates["prompt"] / 1_000_000.0,
                "completion": rates["completion"] / 1_000_000.0,
            }
            for m, rates in self.pricing_service.pricing_table.items()
        }

    def compute_cost(
        self,
        provider: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        res = self.pricing_service.calculate_cost(
            provider, model_name, prompt_tokens, completion_tokens
        )
        if res.cost_status == "UNPRICED":
            raise InvalidPricingModelError(
                f"Model {model_name} not found in pricing table"
            )
        return res.total_cost_usd
