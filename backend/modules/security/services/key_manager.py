class KeyManager:
    def __init__(self):
        self._keys = {}

    def rotate_key(self, tenant_id: str, provider: str, new_key: str):
        self._keys[f"{tenant_id}:{provider}"] = new_key
        return True

    def get_key(self, tenant_id: str, provider: str) -> str | None:
        return self._keys.get(f"{tenant_id}:{provider}")
