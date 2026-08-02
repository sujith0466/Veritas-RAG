"""Cache Serialization Utilities.

Provides strict, standardized serialization for Redis cache values.
Supports JSON, UUIDs, Datetimes (UTC), and Pydantic models.
Pickle is strictly prohibited for security and cross-language compatibility.
"""

from datetime import UTC, datetime
import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CacheJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Cache serialization."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            # Pydantic v2 model dump
            return obj.model_dump(mode="json")
        if isinstance(obj, datetime):
            # Force UTC timezone awareness if naive, then convert to ISO format
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=UTC)
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        return super().default(obj)


class CacheSerializer:
    """Standardized serialization utility for Redis cache values."""

    @classmethod
    def serialize(cls, value: Any) -> str:
        """Serialize a Python object to a JSON UTF-8 string.

        Args:
            value: The object to serialize.

        Returns:
            JSON string representation.
        """
        # If it's already a string, int, or float, just return string rep to save space,
        # unless it needs to be strictly JSON. Let's serialize everything as JSON
        # to ensure deserialization type safety, except raw strings to avoid double quotes if preferred.
        # But to be safe and consistent with "Standardize serialization: JSON, UTF-8", use JSON for all.
        return json.dumps(value, cls=CacheJSONEncoder)

    @classmethod
    def deserialize(cls, value: str | bytes | None) -> Any:
        """Deserialize a JSON UTF-8 string to a Python object.

        Args:
            value: The JSON string or bytes from Redis.

        Returns:
            The parsed Python object or None.
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Fallback for plain strings that were not JSON encoded (e.g. simple SET)
            return value
