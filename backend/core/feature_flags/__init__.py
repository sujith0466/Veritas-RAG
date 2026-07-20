"""Feature flags package for RAGuard AI."""

from backend.core.config import get_settings


def is_enabled(flag_name: str) -> bool:
    """Check if a named feature flag is enabled.

    Args:
        flag_name: The attribute name on FeatureFlagSettings
                   (e.g., "enable_retry_engine").

    Returns:
        True if the flag is enabled, False otherwise.
        Returns False for unknown flag names (safe default).
    """
    features = get_settings().features
    return bool(getattr(features, flag_name, False))


__all__ = ["is_enabled"]
