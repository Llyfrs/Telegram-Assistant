import asyncio
import logging
import re
import time

import pytz
import schedule
import requests
import telegram
import inspect


import telegramify_markdown

from modules.database import ValkeyDB
from modules.reminder import convert_seconds_to_hms


def reqwest(url):
    return requests.get(url).json()


def remove_between_angle_brackets(text):
    cleaned_text = re.sub(r'<.*?>', '', text)  # Remove text between < and >
    return re.sub(r'\s+', ' ', cleaned_text).strip()  # Replace multiple spaces with a single space and strip extra spaces


def generate_progress_bar(value, max_value, length=10):
    progress = int(value / max_value * length)
    return f"\[{'#' * progress}{'-' * (length - progress)}\]"

def logg_error(function):

    async def wrapper(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except Exception as e:
            logging.error(f"Failed to run {function.__name__}: {e}")
            return None

    return wrapper

class Torn:

    def __init__(self, bot , api_key, chat_id):
        self.api_key = api_key
        self.bot : telegram.Bot = bot
        self.chat_id = chat_id
        self.running = True

        self.bounties = None
        self.user = None
        self.company = None


        self.discovered_bounties = []
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


            ## 5 is the error code for when API key runs out of requests, we can wait for it to reset, otherwise we just break and log the error
            if response.get("error").get("code") != 5:

                await self.send("Torn API error: {0}".format(response.get("error").get("error")))
                logging.error("Torn API error: {0}".format(response.get("error").get("error")))

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
            return cache


        url = f'http://www.lol-manager.com/api/battlestats/{self.api_key}/{id}/9.0.5'
        headers = {
            'Content-Type': 'application/json',
        }

        try:
            result = requests.get(url, headers=headers).json()

            if result.get("TargetId") is not None:
                db.set_serialized(f"bts:{id}", result, expire=86400*10)
                return result
            else:
                logging.error(f"Unexpected response from lol-manager {result}")
                return None
        except Exception as e:
            logging.error(f"Failed to get bts data: {e}")

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

        if self.user.get("basicicons").get("icon35", None) is None:
            await self.clear()
            return

        status = self.user.get("status")
        if status.get("state") == "Okay" or status.get("state") == "Hospital":
            hospital_end = self.user.get("states").get("hospital_timestamp")
            message = ""

            if hospital_end == 0:
                message = "You have your bazaar open and are out of hospital!!!"

            hospital_end = hospital_end - time.time()

            if 600 > hospital_end > 0:
                message = f"You have your bazaar open and will be leaving hospital in `{convert_seconds_to_hms(round(hospital_end))}`!!! "

            message += "[Hosp](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=medical) your self now, or close your [bazaar](https://www.torn.com/bazaar.php#/)"

            if hospital_end < 600:
                logging.info("User is in hospital and has bazaar open, sending alert")
                await self.send(message)


    async def newevents(self):
        newevents = self.user.get("events")

        events = []

        for event_id in newevents:
            if newevents[event_id].get("timestamp") > self.oldest_event:
                self.oldest_event = newevents[event_id].get("timestamp")
                events.append(remove_between_angle_brackets(newevents[event_id].get("event")))


        if len(events) > 0:
            logging.info("New event found, sending alert")
            await self.send("*Events*\n\n" + "\n".join(events), clean=False)

    async def bars(self):
        energy = self.user.get("energy")
        nerve = self.user.get("nerve")

        head = "Bars Alert"
        message = head

        if self.user.get("status").get("state") in ["Abroad", "Traveling"]:
            return


        if energy.get("current") == energy.get("maximum") and not self.is_stacking:
            message += f"\n> Your energy is *full*, use it at [gym](https://www.torn.com/gym.php) 💚"
        elif energy.get("current") > energy.get("maximum") * 0.9 and not self.is_stacking:
            message += f"\n> Your energy is almost full, use it at [gym](https://www.torn.com/gym.php) 💚"

        if nerve.get("current") == nerve.get("maximum"):
            message += f"\n> Your nerve is *full*, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"
        elif nerve.get("current") > nerve.get("maximum") * 0.9:
            message += f"\n> Your nerve is almost full, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"


        if message != head:
            await self.send(message)
        else:
            await self.clear()


    @logg_error
    async def stock(self):

        company_stock = self.company.get("company_stock")
        storage_space = self.company.get("company_detailed").get("upgrades").get("storage_space")

        total_sold = sum(float(v["sold_amount"]) for v in company_stock.values())
        total_in_stock = sum(float(v["in_stock"]) + float(v["on_order"]) for v in company_stock.values())

        aim_ratio = storage_space / total_sold
        capacity = storage_space - total_in_stock
        run_out = False

        message = "*Stock Alert*:\n"

        message += f"Capacity to fill: {capacity}\n"
        message += f"Global ratio: {aim_ratio:.2f}\n"

        for key, value in company_stock.items():
            sold = float(value["sold_amount"])
            in_stock = float(value["in_stock"]) + float(value["on_order"])

            diff = aim_ratio - (in_stock / sold)

            if diff <= 0.0:
                print(f"{key}: 0 ({in_stock / sold:.2f})")
            else:
                buy = diff * sold
                capacity -= buy

                if run_out:
                    buy = 0.0
                elif capacity <= 0.0:
                    run_out = True
                    buy = capacity + buy

                message += f"{key}: {buy:.0f} ({in_stock / sold:.2f})\n"

        message += f"Capacity: {round(capacity,2)}"

        await self.send(message)

    async def trains(self):
        try:
            if self.company.get("company_detailed").get("trains_available") == 0:
                messages = "You have no trains available, you can't train anyone"
                logging.info("No trains available")
            else:
                employees = self.company.get("company_employees")
                order : list = ValkeyDB().get_serialized("last_employee_trained", [])

                emp = [ id for id in employees]
                for id in employees:
                    if employees[id].get("wage") > 0:
                        if id not in order:
                            order.append(id)

                for id in order:
                    if id not in emp:
                        order.remove(id)

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


    async def get_valid_bounties(self, min_money):
        await self.update_bounties()


        monitor = []
        ids = []
        skipped = [0,0]

        my_bts = self.user.get("total")
        bounties = self.bounties.get("bounties")


        for bounty in bounties:
            if bounty.get("reward") >= min_money:

                ## Prevents multiple bounties on single person, keeps it clean
                if bounty.get("target_id") in ids:
                    continue

                ids.append(bounty.get("target_id"))

                ## Since I'm caching the bts, it'
                #
                # s better to call it first to save on API calls
                bts = await self.get_bts(bounty.get("target_id"))

                if bts.get("TBS") > my_bts * 1.1:
                    continue

                user_info = await self.get_basic_user(bounty.get("target_id"))
                if user_info.get("basicicons").get("icon71") is not None:
                    continue

                if user_info.get("basicicons").get("icon72") is not None:
                    continue

                user_info["reward"] = bounty.get("reward")
                user_info["TBS"] = bts.get("TBS")

                user_info["valid_until"] = bounty.get("valid_until")


                monitor.append(user_info)

        return monitor

    @logg_error
    async def bounty_monitor(self):

        my_bts = self.user.get("total")
        chat_message : telegram.Message = await self.send("Starting Bounty monitor")

        while True:

            monitor = await self.get_valid_bounties(500000)

            monitor.sort(key=lambda x: x.get("states").get("hospital_timestamp"))

            energy = self.user.get("energy").get("current")
            message = f"*Bounty Monitor ({energy}e)*\n\n"

            for user in monitor:

                reward = "${:,.0f}".format(user.get("reward"))
                bts = round(user.get("TBS") / my_bts * 100)

                message += f"[{user.get('name')}](https://www.torn.com/loader.php?sid=attack&user2ID={user.get('player_id')}) - {reward} "
                message += user.get("status").get("description") + f" ({bts}%)\n"


            message += "\n\nupdated: " + time.strftime('%H:%M:%S', time.localtime())

            message = telegramify_markdown.markdownify(message)
            await chat_message.edit_text(message, parse_mode="MarkdownV2")
            """
            for i in range(0, 20):
                copy = message
                copy += generate_progress_bar(i, 20, length=20)
                await chat_message.edit_text(copy, parse_mode="MarkdownV2")
                await asyncio.sleep(3)
            """
            await asyncio.sleep(60)


    async def bounty_watcher(self):
        min_money = 1000000
        monitor = await self.get_valid_bounties(min_money)
        update_discovered = []
        count = 0
        highest = 0

        new_bounties = []

        for bounty in monitor:
            record = (bounty.get("player_id"), bounty.get("valid_until"))

            if record not in self.discovered_bounties:
                new_bounties.append(bounty)
                count += 1

            update_discovered.append(record)


        self.discovered_bounties = update_discovered

        for bounty in new_bounties:
            logging.info(f"New bounty found: {bounty.get('name')} with ${bounty.get('reward')}, creating watcher")
            asyncio.run_coroutine_threadsafe(self.watch_player_bounty(bounty), asyncio.get_event_loop())


    async def watch_player_bounty(self, player_info):
        ## How long before the player leaves hospital should the bot send the message
        limit = 80

        now = time.time()
        hospital = player_info.get("states").get("hospital_timestamp")

        await asyncio.sleep(hospital - now - limit)

        logging.info(f"Expected wait time: {hospital - now - limit}")
        logging.info(f"Actual wait time: {time.time() - now}")

        user_info = await self.get_basic_user(player_info.get("player_id"))

        ## User no loger has a bounty on them
        if user_info.get("basicicons").get("icon13") is None:
            return

        ## User is in hospital but the hospitalization time increased (probably got attacked or selfhosped)
        ## Spawns new watcher
        if user_info.get("states").get("hospital_timestamp") != hospital:
            player_info["states"] = user_info.get("states")
            asyncio.run_coroutine_threadsafe(self.watch_player_bounty(player_info), asyncio.get_event_loop())
            return

        reward = "${:,.0f}".format(player_info.get("reward"))
        message = await self.send(
            f"{user_info.get('name')} is about to leave hospital with a bounty of {reward}. "
            f"[Attack](https://www.torn.com/loader.php?sid=attack&user2ID={player_info.get('player_id')})")


        ## Delete message when user leaves hospital (not relevant anymore)
        await asyncio.sleep(limit)
        await message.delete()




    ##warper

    @logg_error
    async def run (self):
        logging.info("Torn is up and running")
        cet = pytz.timezone('CET')

        logging.info( await self.get_bts(2531272))

        loop = asyncio.get_event_loop()

        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.update_user(), loop))
        schedule.every(30).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.newevents(), loop))
        schedule.every(10).seconds.do(lambda : asyncio.run_coroutine_threadsafe(self.bazaar_alert(), loop))
        schedule.every(10).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.bars(), loop))
        schedule.every(5).minutes.do(lambda : asyncio.run_coroutine_threadsafe(self.cooldowns(), loop))

        schedule.every().day.at("06:50", cet).do(lambda: asyncio.run_coroutine_threadsafe(self.update_company(), loop))
        schedule.every(30).minutes.do(lambda: asyncio.run_coroutine_threadsafe(self.bounty_watcher(), loop))

        schedule.run_all()

        schedule.every().day.at("07:00", cet).do(lambda : asyncio.run_coroutine_threadsafe(self.stock(), loop))
        schedule.every().day.at("07:00", cet).do(lambda: asyncio.run_coroutine_threadsafe(self.trains(), loop))

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)

