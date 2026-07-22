from backend.modules.marketplace.schemas.marketplace_dto import AppBundleDTO


class MarketplaceRegistry:
    def __init__(self):
        self._bundles: dict[str, AppBundleDTO] = {}

    def publish_bundle(self, bundle: AppBundleDTO):
        self._bundles[bundle.bundle_id] = bundle
        return True

    def get_bundle(self, bundle_id: str) -> AppBundleDTO | None:
        return self._bundles.get(bundle_id)
