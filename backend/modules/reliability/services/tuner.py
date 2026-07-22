from backend.modules.reliability.schemas.reliability_dto import \
    ParameterOverrideDTO


class AdaptiveParameterTuner:
    def __init__(self):
        self._mock_redis = {}

    async def apply_tuning(
        self, tenant_id: str, diagnosis: str
    ) -> ParameterOverrideDTO:
        overrides = ParameterOverrideDTO()
        if diagnosis == "LOW_RECALL":
            overrides.retrieval_top_k = 10
            overrides.similarity_threshold = 0.68
        elif diagnosis == "HIGH_CONFLICT":
            overrides.max_retry_budget = 3
            overrides.reflection_strictness = 0.9

        self._mock_redis[f"raguard:tuning:overrides:{tenant_id}"] = (
            overrides.model_dump()
        )
        return overrides

    async def get_active_overrides(self, tenant_id: str) -> ParameterOverrideDTO | None:
        data = self._mock_redis.get(f"raguard:tuning:overrides:{tenant_id}")
        return ParameterOverrideDTO(**data) if data else None
