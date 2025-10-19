import fnmatch
import logging
import os

import pickle
import valkey
from valkey.exceptions import ConnectionError as ValkeyConnectionError


class _InMemoryValkey:
    """A minimal in-memory fallback that mimics the valkey client API we use."""

    def __init__(self):
        self._store = {}

    def ping(self):
        return True

    def set(self, key, value, ex=None):  # noqa: ARG002 - 'ex' kept for parity
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)

    def scan(self, cursor: int = 0, match: str | None = None):
        if match is None:
            keys = list(self._store.keys())
        else:
            keys = [key for key in self._store.keys() if fnmatch.fnmatch(key, match)]
        return 0, [key.encode("utf-8") for key in keys]


class ValkeyDB:
    valkey_client : valkey.Valkey = None
    cache = {}
    def __init__(self):
        valkey_uri = os.getenv("VALKEY_URI")
        if ValkeyDB.valkey_client is None:
            ValkeyDB.valkey_client = self._init_client(valkey_uri)


        self.valkey_client = ValkeyDB.valkey_client
        ValkeyDB.cache = {}

    @staticmethod
    def _init_client(valkey_uri: str | None):
        if not valkey_uri:
            logging.warning("VALKEY_URI not provided. Using in-memory database fallback.")
            return _InMemoryValkey()

        try:
            client = valkey.from_url(valkey_uri)
            # Force a connection to ensure credentials/network are valid.
            client.ping()
            return client
        except (ValkeyConnectionError, OSError) as error:
            logging.warning(
                "Failed to connect to Valkey at %s (%s). Falling back to in-memory storage.",
                valkey_uri,
                error,
            )
            return _InMemoryValkey()

    def set(self, key: str, value, expire: int = None):
        self.valkey_client.set(key, value, ex=expire)
        ValkeyDB.cache[key] = value


    def get(self, key: str, default=None):

        if key in ValkeyDB.cache:
            return ValkeyDB.cache[key]

        value = self.valkey_client.get(key)
        if value is None:
            return default
        else:
            return value

    def set_serialized(self, key: str, value, expire: int = None):
        bytes_value = pickle.dumps(value)
        self.set(key, bytes_value, expire)

    def get_serialized(self, key: str, default=None):

        value = self.get(key, default)

        if value is default:
            return default

        if isinstance(value, (bytes, bytearray)):
            try:
                return pickle.loads(value)
            except Exception as ex:
                logging.error(f"Failed deserialization {ex}, returning default {default}")
                return default

        logging.debug("Value for key %s is not serialized bytes. Returning default.", key)
        return default

    def delete(self, key: str):
        self.valkey_client.delete(key)
        if key in ValkeyDB.cache:
            del ValkeyDB.cache[key]

    def list(self, prefix: str):

        keys = []
        for key in self.valkey_client.scan(match=prefix + "*")[1]:
            keys.append(key.decode("utf-8"))
        return keys
