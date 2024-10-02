import asyncio
import logging
from time import sleep
from unicodedata import lookup

import schedule
from telegram.constants import ParseMode

from modules.Settings import Settings
import requests

import telegramify_markdown

from modules.database import ValkeyDB


def reqwest(url):
    return requests.get(url).json()


class Torn:

    def __init__(self, bot , api_key, chat_id):
        self.api_key = api_key
        self.bot = bot
        self.chat_id = chat_id
        self.running = True
        self.user = None

    async def send(self, text):
        text = telegramify_markdown.markdownify(text)
        await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="MarkdownV2")


    async def get(self, url):
        response = requests.get(url).json()

        while response.get("error") is not None:

            await self.send(response.get("error").get("error"))
            if response.get("error").get("code") == 5:
                break

            response = requests.get(url).json()
            await asyncio.sleep(10)

        return response


    async def get_user(self):
        url = f"https://api.torn.com/user/?selections=profile,cooldowns,newevents&key={self.api_key}"
        return await self.get(url)


    async def update_user(self):

        await self.send("Updating user data")

        try :
            self.user = await self.get_user()
        except Exception as e:
            logging.error(f"Failed to get user data: {e}")
            return

    async def cooldowns(self):
        cooldowns = self.user.get("cooldowns")
        status = self.user.get("status")

        ## Tell player to use up their cooldowns if they can
        if status.get("state") == "Okay" or status.get("state") == "Hospitalized":

            if cooldowns.get("drug") == 0:
                await self.send("Take Xanax [here](https://www.torn.com/item.php#drugs-items)")

            if cooldowns.get("medical") == 0:
                await self.send("Use Blood Bag")

            if cooldowns.get("booster") == 0:
                await self.send("You have empty booster, fill it up")


    async def run (self):

        logging.info("Torn is up and running")
        await self.send("*Torn is now running*")





        schedule.every(1).minutes.do(self.update_user)
        schedule.every(5).minutes.do(self.cooldowns)
        schedule.run_all()


        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)

