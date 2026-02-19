from __future__ import annotations

import fnmatch
import os
from datetime import datetime, timedelta
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from utils.logging import get_logger

logger = get_logger(__name__)


class _InMemoryMongo:
    """A minimal in-memory fallback that mimics MongoDB operations."""

    def __init__(self):
        self._collections: dict[str, dict[str, dict]] = {}

    def ping(self):
        return True

    def get_collection(self, name: str) -> _InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = {}
        return _InMemoryCollection(self._collections[name])


class _InMemoryCollection:
    """In-memory collection that mimics PyMongo Collection API."""

    def __init__(self, store: dict[str, dict]):
        self._store = store

    def find_one(self, filter: dict) -> dict | None:
        for doc in self._store.values():
            if self._matches(doc, filter):
                return doc.copy()
        return None

    def find(self, filter: dict | None = None) -> list[dict]:
        filter = filter or {}
        return [doc.copy() for doc in self._store.values() if self._matches(doc, filter)]

    def insert_one(self, document: dict):
        key = str(document.get("_id", id(document)))
        self._store[key] = document.copy()

    def update_one(self, filter: dict, update: dict, upsert: bool = False):
        for key, doc in self._store.items():
            if self._matches(doc, filter):
                if "$set" in update:
                    doc.update(update["$set"])
                return
        if upsert and "$set" in update:
            new_doc = {**filter, **update["$set"]}
            key = str(new_doc.get("_id", id(new_doc)))
            self._store[key] = new_doc

    def delete_one(self, filter: dict):
        for key, doc in list(self._store.items()):
            if self._matches(doc, filter):
                del self._store[key]
                return

    def delete_many(self, filter: dict):
        to_delete = [key for key, doc in self._store.items() if self._matches(doc, filter)]
        for key in to_delete:
            del self._store[key]

    def count_documents(self, filter: dict) -> int:
        return len([doc for doc in self._store.values() if self._matches(doc, filter)])

    def _matches(self, doc: dict, filter: dict) -> bool:
        for key, value in filter.items():
            if key not in doc:
                return False
            if isinstance(value, dict):
                # Handle MongoDB operators
                for op, op_value in value.items():
                    if op == "$gte" and not (doc[key] >= op_value):
                        return False
                    elif op == "$lte" and not (doc[key] <= op_value):
                        return False
                    elif op == "$gt" and not (doc[key] > op_value):
                        return False
                    elif op == "$lt" and not (doc[key] < op_value):
                        return False
                    elif op == "$regex" and not fnmatch.fnmatch(str(doc[key]), value.get("$regex", "*")):
                        return False
            elif doc[key] != value:
                return False
        return True


class MongoDB:
    """MongoDB client with key-value store and collection access."""

    _client: ClassVar[MongoClient | _InMemoryMongo | None] = None
    _db: ClassVar[Database | _InMemoryMongo | None] = None

    def __init__(self):
        if MongoDB._client is None:
            MongoDB._client, MongoDB._db = self._init_client()

    @staticmethod
    def _init_client() -> tuple[MongoClient | _InMemoryMongo, Database | _InMemoryMongo]:
        mongo_uri = os.getenv("MONGODB_URI")

        if not mongo_uri:
            logger.warning("MONGODB_URI not provided. Using in-memory database fallback.")
            fallback = _InMemoryMongo()
            return fallback, fallback

        try:
            client = MongoClient(mongo_uri)
            client.admin.command("ping")
            db_name = os.getenv("MONGODB_DATABASE", "telegram_assistant")
            db = client[db_name]
            logger.info("Connected to MongoDB database: %s", db_name)
            return client, db
        except ConnectionFailure as error:
            logger.warning(
                "Failed to connect to MongoDB at %s (%s). Falling back to in-memory storage.",
                mongo_uri,
                error,
            )
            fallback = _InMemoryMongo()
            return fallback, fallback

    def _kv_collection(self) -> Collection | _InMemoryCollection:
        """Get the key-value store collection."""
        if isinstance(MongoDB._db, _InMemoryMongo):
            return MongoDB._db.get_collection("kv_store")
        return MongoDB._db["kv_store"]

    def collection(self, name: str) -> Collection | _InMemoryCollection:
        """Get a named collection for structured document storage."""
        if isinstance(MongoDB._db, _InMemoryMongo):
            return MongoDB._db.get_collection(name)
        return MongoDB._db[name]

    # ─────────────────────────────────────────────────────────────────────────────
    # Key-Value Store Methods
    # ─────────────────────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any, expire: int | None = None) -> None:
        """Set a key-value pair. Optional expire in seconds."""
        doc = {"_id": key, "value": value}
        if expire is not None:
            doc["expires_at"] = datetime.utcnow() + timedelta(seconds=expire)
        self._kv_collection().update_one({"_id": key}, {"$set": doc}, upsert=True)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by key. Returns default if not found or expired."""
        doc = self._kv_collection().find_one({"_id": key})
        if doc is None:
            return default

        # Check expiration
        expires_at = doc.get("expires_at")
        if expires_at and datetime.utcnow() > expires_at:
            self.delete(key)
            return default

        return doc.get("value", default)

    def delete(self, key: str) -> None:
        """Delete a key-value pair."""
        self._kv_collection().delete_one({"_id": key})

    def list(self, prefix: str) -> list[str]:
        """List all keys matching a prefix."""
        # For real MongoDB, use regex; for in-memory, fnmatch handles it
        if isinstance(MongoDB._db, _InMemoryMongo):
            docs = self._kv_collection().find({})
            return [doc["_id"] for doc in docs if doc["_id"].startswith(prefix)]
        else:
            docs = self._kv_collection().find({"_id": {"$regex": f"^{prefix}"}})
            return [doc["_id"] for doc in docs]


# ─────────────────────────────────────────────────────────────────────────────
# Document Base Class for Typed Collections
# ─────────────────────────────────────────────────────────────────────────────

class Document(BaseModel):
    """
    Base class for MongoDB documents with automatic serialization.

    Usage:
        class User(Document):
            model_config = ConfigDict(collection_name="users")

            name: str
            email: str

        # Save
        user = User(name="John", email="john@example.com")
        user.save()

        # Query
        users = User.find(name="John")
        user = User.find_one(email="john@example.com")

        # Delete
        User.delete_one(name="John")
    """

    model_config = ConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    _registry: ClassVar[list[type["Document"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Document._registry.append(cls)

    @classmethod
    def ensure_indexes(cls):
        """Override in subclasses to define indexes."""
        pass

    @classmethod
    def ensure_all_indexes(cls):
        """Initialize indexes for all registered Document subclasses."""
        for doc_class in Document._registry:
            doc_class.ensure_indexes()

    @classmethod
    def _get_collection_name(cls) -> str:
        """Get collection name from model_config or use class name."""
        config = cls.model_config
        if isinstance(config, dict) and "collection_name" in config:
            return config["collection_name"]
        return cls.__name__.lower() + "s"

    @classmethod
    def _collection(cls) -> Collection | _InMemoryCollection:
        """Get the MongoDB collection for this document type."""
        return MongoDB().collection(cls._get_collection_name())

    def save(self, key_field: str | None = None) -> None:
        """
        Save this document to MongoDB.

        Args:
            key_field: Field to use as unique identifier for upsert.
                       If None, always inserts a new document.
        """
        data = self.model_dump(mode="json")

        if key_field and key_field in data:
            self._collection().update_one(
                {key_field: data[key_field]},
                {"$set": data},
                upsert=True
            )
        else:
            self._collection().insert_one(data)

    @classmethod
    def find(cls, **query) -> list[Self]:
        """Find all documents matching the query."""
        docs = cls._collection().find(query)
        return [cls.model_validate(doc) for doc in docs]

    @classmethod
    def find_one(cls, **query) -> Self | None:
        """Find a single document matching the query."""
        doc = cls._collection().find_one(query)
        if doc is None:
            return None
        return cls.model_validate(doc)

    @classmethod
    def delete_one(cls, **query) -> None:
        """Delete a single document matching the query."""
        cls._collection().delete_one(query)

    @classmethod
    def delete_many(cls, **query) -> None:
        """Delete all documents matching the query."""
        cls._collection().delete_many(query)


# Backward compatibility alias
ValkeyDB = MongoDB
