import logging
import os
from mailcap import lookup

import valkey
import pickle

from valkey import Valkey


class ValkeyDB:
    valkey_client = None
    def __init__(self):
        valkey_uri = os.getenv("VALKEY_URI")
        if ValkeyDB.valkey_client is None:
            ValkeyDB.valkey_client = valkey.from_url(valkey_uri)


        self.valkey_client = ValkeyDB.valkey_client
        self.cache = {}

    def set(self, key: str, value):
        self.valkey_client.set(key, value)
        self.cache[key] = value

    def get(self, key: str, default=None):

        if key in self.cache:
            return self.cache[key]

        value = self.valkey_client.get(key)
        if value is None:
            return default
        else:
            return value

    def set_serialized(self, key: str, value):
        bytes = pickle.dumps(value)
        self.set(key, bytes)

    def get_serialized(self, key: str, default=None):

        bytes = self.get(key, default)

        try:
            return pickle.loads(bytes)
        except Exception as ex:
            logging.error(f'Failed deserialization {ex}, returning default {default}')
            return default

