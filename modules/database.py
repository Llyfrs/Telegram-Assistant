import logging
import os
from nis import match

import valkey
import pickle


class ValkeyDB:
    valkey_client : valkey.Valkey = None
    cache = {}
    def __init__(self):
        valkey_uri = os.getenv("VALKEY_URI")
        if ValkeyDB.valkey_client is None:
            ValkeyDB.valkey_client = valkey.from_url(valkey_uri)


        self.valkey_client = ValkeyDB.valkey_client
        ValkeyDB.cache = {}

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
        bytes = pickle.dumps(value)
        self.set(key, bytes,expire)

    def get_serialized(self, key: str, default=None):

        bytes = self.get(key, default)

        try:
            return pickle.loads(bytes)
        except Exception as ex:
            logging.error(f'Failed deserialization {ex}, returning default {default}')
            return default

    def delete(self, key: str):
        self.valkey_client.delete(key)
        if key in ValkeyDB.cache:
            del ValkeyDB.cache[key]

    def list(self, prefix: str):

        keys = []
        for key in self.valkey_client.scan(match = prefix + "*")[1]:
            keys.append(key.decode("utf-8"))

        return keys