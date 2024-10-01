import asyncio
import logging

from modules.Settings import Settings
import requests


def reqwest(url):
    return requests.get(url).json()


class Torn:

    def __init__(self):
        self.api_key = None
        self.settings = Settings("settings")
        self.api_key = self.settings.get_setting("torn_api")

    async def run (selft):
        while True:
            logging.info("Test")
            await asyncio.sleep(10)
