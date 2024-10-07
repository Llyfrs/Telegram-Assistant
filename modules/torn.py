import asyncio
import logging
import re
import time
from pyexpat.errors import messages

import pytz
import schedule
import requests
import telegram
import inspect
import subprocess

import telegramify_markdown
from requests.packages import target
from telebot.types import Message
from telegram import MessageEntity

from modules.database import ValkeyDB
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

        self.bounties = None
        self.user = None
        self.company = None

        self.oldest_event = 0
        self.last_messages= {}
        self.is_stacking = False

    def set_stacking(self, value):
        self.is_stacking = value

    def get_stacking(self):
        return self.is_stacking

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
        try:
            text = telegramify_markdown.markdownify(text)
            message = await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="MarkdownV2")

            ## Wild stuff this is, but it makes sure the bot cleans up after itself, at the same time it sends new message
            try:
                if inspect.stack()[1].function in self.last_messages and clean:
                    await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_messages[inspect.stack()[1].function].message_id)
            except Exception as e:
                logging.error(f"Failed to clean last message: {e} in message: {text}")

            self.last_messages[inspect.stack()[1].function] = message
            return message

        except Exception as e:
            logging.error(f"Failed to send message: {e} in message: {text}")

    async def get(self, url):
        response = requests.get(url).json()

        while response.get("error") is not None:

            await self.send(f"Torn API error: {response.get("error").get("error")}")
            logging.error(f"Torn API error: {response.get("error").get("error")}")
            if response.get("error").get("code") != 5:
                break

            response = requests.get(url).json()
            await asyncio.sleep(10)

        return response


    async def get_user(self):
        url = f"https://api.torn.com/user/?selections=profile,cooldowns,newevents,bars,battlestats&key={self.api_key}"
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

    ## Example of returned value:
    ## {
    # 'Result': 1, 'TargetId': 2531272, 'TBS_Raw': 2984136331, 'TBS': 2984136331, 'TBS_Balanced': 2812817296,
    # 'Score': 106072, 'Version': 50, 'Reason': '', 'SubscriptionEnd': '2024-10-14T09:29:31.2237362Z',
    # 'PredictionDate': '2024-10-07T03:35:03.4366667'
    # }
    async def get_bts(self, id):

        db = ValkeyDB()
        cache = db.get_serialized(f"bts:{id}", None)

        if cache is not None:
            logging.info(f"Using cache for bts:{id}")
            return cache


        url = f'http://www.lol-manager.com/api/battlestats/{self.api_key}/{id}/9.0.5'
        headers = {
            'Content-Type': 'application/json',
        }

        result = requests.get(url, headers=headers).json()

        if result.get("TargetId") is not None:
            db.set_serialized(f"bts:{id}", result, expire=86400*10)
            return result
        else:
            logging.error(f"Unexpected response from lol-manager {result}")
            return None


    async def update_user(self):
        try :
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

            try:
                if 600 > hospital_end > 0:
                    message = f"You have your bazaar open and will be leaving hospital in `{convert_seconds_to_hms(round(hospital_end))}`!!! "
                else:
                    return # No need to send message if it's not close to the end
            except Exception as e:
                logging.error(f"Failed to check hospital time: {e}")

            message += "[Hosp](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=medical) your self now, or close your [bazaar](https://www.torn.com/bazaar.php#/)"

            logging.info("User is in hospital and has bazaar open, sending alert")

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


        if energy.get("current") == energy.get("maximum") and not self.is_stacking:
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


    async def trains(self):
        try:
            if self.company.get("company_detailed").get("trains_available") == 0:
                messages = "You have no trains available, you can't train anyone"
                logging.info("No trains available")
            else:
                employees = self.company.get("company_employees")
                order : list = ValkeyDB().get_serialized("last_employee_trained", [])

                for id in employees:
                    if employees[id].get("wage") > 0:
                        if id not in order:
                            order.append(id)


                order.append(order.pop(0))
                ValkeyDB().set_serialized("last_employee_trained", order)



                wage = employees[order[0]].get("wage")
                trains = self.company.get("company_detailed").get("trains_available")

                messages = (f"You have *{trains} trains* available and your next employee to train is *{employees[order[0]].get('name')}* "
                            f"you can update their wage to `{wage - trains}` when you finish. [Quick link](https://www.torn.com/companies.php?step=your&type=1)")

                logging.info(f"Trains available: {trains}, next employee: {employees[order[0]].get('name')}")

        except Exception as e:
            logging.error(f"Failed to get train data: {e}")
            return


        await self.send(messages)


    async def bounty_monitor(self):

        my_bts = self.user.get("total")
        chat_message : telegram.Message = await self.send("Starting Bounty monitor")

        while True:

            await self.update_bounties()

            monitor = []
            ids= []

            bounties = self.bounties.get("bounties")
            monitor.clear()
            for bounty in bounties:
                if bounty.get("reward") >= 500000:

                    ## Prevents multiple bounties on single person, keeps it clean
                    if bounty.get("target_id") in ids:
                        continue

                    ids.append(bounty.get("target_id"))


                    ## Since I'm caching the bts, it's better to call it first to save on API calls
                    bts = await self.get_bts(bounty.get("target_id"))

                    if bts.get("TBS") > my_bts * 1.1:
                        logging.info(f"Skipping {bounty.get("target_id")} because of bts {bts.get('TBS')} vs {my_bts}")
                        continue

                    user_info = await self.get_basic_user(bounty.get("target_id"))
                    if user_info.get("basicicons").get("icon71") is not None:
                        logging.info(f"Skipping {user_info.get('name')} because they are aboard")
                        continue

                    logging.info(f"Adding {user_info.get('name')} to monitor")


                    user_info["reward"] = bounty.get("reward")
                    user_info["TBS"] = bts.get("TBS")

                    monitor.append(user_info)


            monitor.sort(key=lambda x: x.get("states").get("hospital_timestamp"))

            message = "*Bounty Monitor*\n\n"

            for user in monitor:

                reward = "${:,.0f}".format(user.get("reward"))
                bts = round(user.get("TBS") / my_bts * 100)

                message += f"[{user.get('name')}](https://www.torn.com/loader.php?sid=attack&user2ID={user.get("player_id")}) - {reward} "
                message += user.get("status").get("description") + f" ({bts}%)\n"




            message += "\n\nupdated: " + time.strftime('%H:%M:%S', time.localtime())

            message = telegramify_markdown.markdownify(message)
            await chat_message.edit_text(message, parse_mode="MarkdownV2")
            await asyncio.sleep(60)



    async def run (self):

        logging.info("Torn is up and running")
        cet = pytz.timezone('CET')

        logging.info( await self.get_bts(2531272))

        loop = asyncio.get_event_loop()
        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.update_user(), loop))
        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.newevents(), loop))
        schedule.every(10).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.bazaar_alert(), loop))
        schedule.every(15).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.bars(), loop))
        schedule.every(5).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.cooldowns(), loop))
        schedule.every().day.at("17:59", cet).do(lambda: asyncio.run_coroutine_threadsafe(self.update_company(), loop))

        schedule.run_all()

        schedule.every().day.at("18:00", cet).do(lambda : asyncio.run_coroutine_threadsafe(self.stock(), loop))
        schedule.every().day.at("18:00", cet).do(lambda: asyncio.run_coroutine_threadsafe(self.trains(), loop))

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)

