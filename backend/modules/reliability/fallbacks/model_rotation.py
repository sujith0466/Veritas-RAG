class ModelRotationOrchestrator:
    def __init__(self):
        self.backup_priority = ["azure-openai", "anthropic", "local-vllm"]
        self._mock_redis = {}

    async def rotate_provider(self, tenant_id: str, failed_provider: str) -> str:
        for backup in self.backup_priority:
            if backup != failed_provider:
                # Mock setting routing override
                self._mock_redis[f"route_override:{tenant_id}"] = backup
                return backup
        raise Exception("All backup providers failed")
