from backend.modules.analytics.schemas.errors import InvalidPricingModelError


class PricingEngine:
    def __init__(self):
        # Micro-dollars per token (e.g. $0.005 per 1K -> 0.000005 per token)
        self.pricing_table = {
            "gpt-4o": {"prompt": 0.000005, "completion": 0.000015},
            "text-embedding-3-large": {"prompt": 0.00000013, "completion": 0.0},
            "anthropic-claude-3-opus": {"prompt": 0.000015, "completion": 0.000075},
        }

    def compute_cost(
        self, provider: str, model_name: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        rates = self.pricing_table.get(model_name)
        if not rates:
            raise InvalidPricingModelError(
                f"Model {model_name} not found in pricing table"
            )
        return (prompt_tokens * rates["prompt"]) + (
            completion_tokens * rates["completion"]
        )
