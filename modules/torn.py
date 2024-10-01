import asyncio
import logging
import schedule

from modules.Settings import Settings
import requests

from modules.database import ValkeyDB


def reqwest(url):
    return requests.get(url).json()


class Torn:

    def __init__(self, bot, api_key, chat_id):
        self.api_key = api_key
        self.bot = bot
        self.chat_id = chat_id

    async def run (selft):

        while True:
            logging.info("Test")
            await asyncio.sleep(10)
