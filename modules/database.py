import os
import valkey
import pickle

class ValkeyDB:
    def __init__(self):
        valkey_uri = os.getenv("VALKEY_URI")
        self.valkey_client = valkey.from_url(valkey_uri)

    def insert(self, key: str, value: str):
        self.valkey_client.set(key, value)

    def get(self, key: str, default=None):
        value = self.valkey_client.get(key)
        if value is None:
            return default
        else:
            return value

    def insert_serialized(self, key: str, value):
        bytes = pickle.dumps(value)
        self.valkey_client.set(key, bytes)

    def get_serialized(self, key: str):
        bytes = self.valkey_client.get(key)
        return pickle.loads(bytes)
