import asyncio
import logging
import re
import time
from typing import Any, Dict, Optional

import requests
import telegram
import inspect

import telegramify_markdown

from modules.database import ValkeyDB


def reqwest(url):
    return requests.get(url).json()


def remove_between_angle_brackets(text: str) -> str:
    cleaned_text = re.sub(r'<.*?>', '', text)
    return re.sub(r'\s+', ' ', cleaned_text).strip()


def logg_error(function):
    async def wrapper(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except Exception as e:
            logging.error(f"Failed to run {function.__name__}: {e}")
            return None

    return wrapper


class Torn:

    def __init__(self, bot: telegram.Bot, api_key: str, chat_id: Optional[int]):
        self.api_key = api_key
        self.bot: telegram.Bot = bot
        self.chat_id = chat_id

        self.bounties: Optional[Dict[str, Any]] = None
        self.user: Optional[Dict[str, Any]] = None
        self.company: Optional[Dict[str, Any]] = None

        self.discovered_bounties = []
        self.oldest_event = 0
        self.last_messages = {}
        self.is_stacking = False

        self.cache: Dict[str, Dict[str, Any]] = {}

    def set_stacking(self, value: bool):
        self.is_stacking = value

    def get_stacking(self) -> bool:
        return self.is_stacking

    async def send_html(self, text: str):
        try:
            return await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="html")
        except Exception as e:
            logging.error(f"Failed to send html message: {e} in message: {text}")

    async def clear(self):
        caller = inspect.stack()[1].function
        if caller in self.last_messages:
            await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_messages[caller].message_id)
            self.last_messages.pop(caller)

    async def send(self, text: str, clean: bool = True):
        try:
            text = telegramify_markdown.markdownify(text)
            message = await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="MarkdownV2")

            try:
                if inspect.stack()[1].function in self.last_messages and clean:
                    await self.bot.delete_message(
                        chat_id=self.chat_id,
                        message_id=self.last_messages[inspect.stack()[1].function].message_id
                    )
            except Exception as e:
                logging.error(f"Failed to clean last message: {e} in message: {text}")

            self.last_messages[inspect.stack()[1].function] = message
            return message

        except Exception as e:
            logging.error(f"Failed to send message: {e} in message: {text}")

    async def get(self, url: str):

        if self.cache.get(url, None) is not None:
            if self.cache[url].get("expires", 0) > time.time():
                return self.cache[url]["data"]

        response = requests.get(url).json()

        while response.get("error") is not None:

            if response.get("error").get("code") != 5:

                await self.send("Torn API error: {0}".format(response.get("error").get("error")))
                logging.error("Torn API error: {0}".format(response.get("error").get("error")))

                break

            response = requests.get(url).json()
            await asyncio.sleep(10)

        if response.get("error") is None:
            self.cache[url] = {
                "data": response,
                "expires": time.time() + 30
            }

        return response

    async def get_user(self):
        url = f"https://api.torn.com/user/?selections=profile,cooldowns,newevents,bars,battlestats,icons&key={self.api_key}"
        return await self.get(url)

    async def get_company(self):
        url = f"https://api.torn.com/company/?selections=employees,detailed,stock&key={self.api_key}"
        return await self.get(url)

    async def get_bounties(self):
        url = f"https://api.torn.com/v2/torn/?selections=bounties&key={self.api_key}"
        return await self.get(url)

    async def get_basic_user(self, id):
        url = f"https://api.torn.com/user/{id}?selections=profile&key={self.api_key}"
        return await self.get(url)

    async def get_targeteds(self, offset=0):
        url = f"https://api.torn.com/v2/user/list?cat=Targets&striptags=true&limit=50&offset={offset}&key={self.api_key}"
        return await self.get(url)

    async def get_bts(self, id):

        db = ValkeyDB()
        cache = db.get_serialized(f"bts:{id}", None)

        if cache is not None:
            return cache

        url = f'http://www.lol-manager.com/api/battlestats/{self.api_key}/{id}/9.0.5'
        headers = {
            'Content-Type': 'application/json',
        }

        try:
            result = requests.get(url, headers=headers).json()

            if result.get("TargetId") is not None:
                db.set_serialized(f"bts:{id}", result, expire=86400 * 10)
                return result
            else:
                logging.error(f"Unexpected response from lol-manager {result}")
                return None
        except Exception as e:
            logging.error(f"Failed to get bts data: {e}")

    async def update_user(self):

        try:
            self.user = await self.get_user()
        except Exception as e:
            logging.error(f"Failed to get user data: {e}")
            return

    async def update_company(self):

        try:
            self.company = await self.get_company()
        except Exception as e:
            logging.error(f"Failed to get company data: {e}")

    async def update_bounties(self):
        try:
            self.bounties = await self.get_bounties()
        except Exception as e:
            logging.error(f"Failed to get bounties data: {e}")
