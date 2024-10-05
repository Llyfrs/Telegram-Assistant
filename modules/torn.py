import asyncio
import logging
import re
import time
from datetime import datetime
from pyexpat.errors import messages

import schedule
import requests
import telegram
import inspect
import subprocess

import telegramify_markdown

from modules.reminder import convert_seconds_to_hms


def reqwest(url):
    return requests.get(url).json()


def remove_between_angle_brackets(text):
    cleaned_text = re.sub(r'<.*?>', '', text)  # Remove text between < and >
    return re.sub(r'\s+', ' ', cleaned_text).strip()  # Replace multiple spaces with a single space and strip extra spaces



class Torn:

    def __init__(self, bot , api_key, chat_id):
        self.api_key = api_key
        self.bot : telegram.Bot = bot
        self.chat_id = chat_id
        self.running = True
        self.user = None
        self.oldest_event = 0
        self.last_messages= {}

    async def cancel(self):
        self.running = False

    async def send_html(self, text):
        try:
            return await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="html")
        except Exception as e:
            logging.error(f"Failed to send html message: {e} in message: {text}")

    async def clear(self):
        caller = inspect.stack()[1].function
        if caller in self.last_messages:
            await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_messages[caller].message_id)
            self.last_messages.pop(caller)

    async def send(self, text, clean = True):
        text = telegramify_markdown.markdownify(text)
        message = await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="MarkdownV2")

        ## Wild stuff this is, but it makes sure the bot cleans up after itself, at the same time it sends new message
        if inspect.stack()[1].function in self.last_messages and clean:
            await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_messages[inspect.stack()[1].function].message_id)
        self.last_messages[inspect.stack()[1].function] = message

    async def get(self, url):
        response = requests.get(url).json()

        while response.get("error") is not None:

            await self.send(response.get("error").get("error"))
            if response.get("error").get("code") != 5:
                break

            response = requests.get(url).json()
            await asyncio.sleep(10)

        return response


    async def get_user(self):
        url = f"https://api.torn.com/user/?selections=profile,cooldowns,newevents,bars&key={self.api_key}"
        return await self.get(url)


    async def update_user(self):
        try :
            self.user = await self.get_user()
        except Exception as e:
            logging.error(f"Failed to get user data: {e}")
            return

    async def cooldowns(self):
        cooldowns = self.user.get("cooldowns")
        status = self.user.get("status")

        message = "*Cooldown Alarms*:"
        ## Tell player to use up their cooldowns if they can
        if status.get("state") == "Okay" or status.get("state") == "Hospitalized":

            if cooldowns.get("drug") == 0:
                message += "\n >Take Xanax 💊 [here](https://www.torn.com/item.php#drugs-items)"

            #if cooldowns.get("medical") == 0: # I mean I could turn it on but I don't want
                #message += "\n > Use blood bag 💉 [here](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=medical)"

            if cooldowns.get("booster") == 0:
                message += "\n > Use boosters 🍺 [here](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=boosters)"

        if message != "*Cooldown Alarms*:":
            await self.send(message)
        else:
            await self.clear()

    async def bazaar_alert(self):

        if "icon35" not in self.user.get("basicicons"):
            await self.clear()
            return


        status = self.user.get("status")
        if status.get("state") == "Okay" or status.get("state") == "Hospital":
            hospital_end = self.user.get("states").get("hospital_timestamp")
            message = ""

            if hospital_end == 0:
                message = "You have your bazaar open and are out of hospital!!!"

            hospital_end = hospital_end - time.time()

            logging.info(f"Hospital end: {hospital_end}")
            try:
                if 600 > hospital_end > 0:
                    message = f"You have your bazaar open and will be leaving hospital in `{convert_seconds_to_hms(round(hospital_end))}`!!! "
                else:
                    return # No need to send message if it's not close to the end
            except Exception as e:
                logging.error(f"Failed to check hospital time: {e}")

            message += "[Hosp](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=medical) your self now, or close your [bazaar](https://www.torn.com/bazaar.php#/)"

            await self.send(message)


    async def newevents(self):
        newevents = self.user.get("events")

        for event_id in newevents:
            if newevents[event_id].get("timestamp") > self.oldest_event:
                self.oldest_event = newevents[event_id].get("timestamp")
                await self.send(remove_between_angle_brackets(newevents[event_id].get("event")), clean=False)

    async def bars(self):
        energy = self.user.get("energy")
        nerve = self.user.get("nerve")

        head = "Bars Alert"
        message = head

        if self.user.get("status").get("state") in ["Abroad", "Traveling"]:
            return


        if energy.get("current") == energy.get("maximum"):
            message += f"\n> Your energy is *full*, use it at [gym](https://www.torn.com/gym.php) 💚"
        elif energy.get("current") > energy.get("maximum") * 0.9:
            message += f"\n> Your energy is almost full, use it at [gym](https://www.torn.com/gym.php) 💚"

        if nerve.get("current") == nerve.get("maximum"):
            message += f"\n> Your nerve is *full*, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"
        elif nerve.get("current") > nerve.get("maximum") * 0.9:
            message += f"\n> Your nerve is almost full, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"


        if message != head:
            await self.send(message)
        else:
            await self.clear()


    ## Small calculator for company stock that I wrote in rust and didn't feel like rewriting it when I can just import the binary
    async def stock(self):
        try:
            result = subprocess.run(["modules/stock_calculator"] + [self.api_key], stdout=subprocess.PIPE)
            result = result.stdout.decode("utf-8")
        except Exception as e:
            logging.error(f"Failed to get stock data: {e}")
            return

        await self.send(result)


    async def run (self):

        logging.info("Torn is up and running")

        loop = asyncio.get_event_loop()
        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.update_user(), loop))
        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.newevents(), loop))
        schedule.every(10).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.bazaar_alert(), loop))
        schedule.every(15).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.bars(), loop))
        schedule.every(5).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.cooldowns(), loop))
        schedule.run_all()

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)

