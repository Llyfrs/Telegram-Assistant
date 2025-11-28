from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pydantic import ConfigDict

from modules.database import Document


class BattleStatsCache(Document):
    """Cache for battle stats predictions with automatic TTL expiration."""

    model_config = ConfigDict(collection_name="bts_cache")

    target_id: int
    data: Dict[str, Any]
    expires_at: datetime

    @classmethod
    def ensure_indexes(cls):
        """Create TTL index on expires_at field for automatic document deletion."""
        collection = cls._collection()
        if hasattr(collection, 'create_index'):
            collection.create_index("expires_at", expireAfterSeconds=0)

    @classmethod
    def get_cached(cls, target_id: int) -> Optional[Dict[str, Any]]:
        """Get cached BTS data for a target, or None if not found/expired."""
        cached = cls.find_one(target_id=target_id)
        if cached is None:
            return None
        # MongoDB TTL handles deletion, but check just in case
        if datetime.utcnow() > cached.expires_at:
            return None
        return cached.data

    @classmethod
    def set_cached(cls, target_id: int, data: Dict[str, Any], expire_days: int = 10) -> None:
        """Cache BTS data for a target with expiration."""
        cache_entry = cls(
            target_id=target_id,
            data=data,
            expires_at=datetime.utcnow() + timedelta(days=expire_days)
        )
        cache_entry.save(key_field="target_id")

