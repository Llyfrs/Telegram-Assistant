import asyncio
import datetime
import time
import threading

import pytz
from telegram.ext import ContextTypes

from modules.database import MongoDB
from utils.logging import get_logger

logger = get_logger(__name__)


class Reminder:
    def __init__(self, seconds: int, chat_id, reminder, bot, loop=None):
        self.reminder = reminder
        self.chat_id = chat_id
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.thread = threading.Timer(seconds, self.run)
        self.thread.start()
        self.bot = bot

    def run(self):
        asyncio.run_coroutine_threadsafe(self.send_reminder(), self.loop)

    async def send_reminder(self):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=self.reminder)
        except Exception as exc:
            logger.error("Error sending reminder: %s", exc)

    def cancel(self):
        self.thread.cancel()


def convert_seconds_to_hms(seconds: int):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def calculate_seconds(days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0):
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def seconds_until(target_date_str : str) -> int:
    # Define Prague time zone
    prague_tz = pytz.timezone('cet')

    # Get the current time in Prague
    now = datetime.datetime.now(prague_tz)

    # Parse the target date string and localize it to Prague time zone
    target_date = prague_tz.localize(datetime.datetime.strptime(target_date_str, '%Y-%m-%d %H:%M:%S'))

    # Calculate the time difference
    time_difference = target_date - now

    logger.debug("Target: %s, Now: %s, Diff: %s", target_date, now, time_difference)

    # Return the total seconds remaining
    return int(time_difference.total_seconds())

class Reminders:
    def __init__(self, bot):
        self.reminders = []
        self.reminder_data: list = []
        self.chat_id = None
        self.bot = bot
        self.db = MongoDB()

        self.loop = asyncio.get_event_loop()

        try:
            temp = self.db.get("reminders")

            for reminder in temp:
                if reminder[0] - time.time() < 0:
                    continue

                self.reminder_data.append(reminder)
                self.reminders.append(Reminder(reminder[0] - time.time(), reminder[2], reminder[1], bot))

        except Exception as exc:
            logger.error("Error loading reminders: %s", exc)

    def add_reminder(self, seconds: int, reminder: str = "reminder"):
        rem = Reminder(seconds, self.chat_id, reminder, self.bot, self.loop)
        self.reminders.append(rem)
        self.reminder_data.append((time.time() + seconds, reminder, self.chat_id))

        self.db.set("reminders", self.reminder_data)

        logger.info("Reminder set for %s from now", convert_seconds_to_hms(seconds))

        return f"Reminder set for {convert_seconds_to_hms(seconds)} from now"

    def get_reminders(self):

        self.remove_finished()

        logger.debug("Getting reminders")

        list_string_data = []
        for i, reminder in enumerate(self.reminder_data):
            list_string_data.append(
                f"{i}: {reminder[1]} finished in {convert_seconds_to_hms(int(reminder[0] - time.time()))}")

        return "\n".join(list_string_data)

    def remove_reminders(self, indexes: list[int]):
        indexes.sort(reverse=True)

        logger.debug("Removing reminders at indexes: %s", indexes)

        for index in indexes:
            self.reminders[index].cancel()
            self.reminders.pop(index)
            self.reminder_data.pop(index)

        self.db.set("reminders", self.reminder_data)

        return "Reminders deleted"

    def remove_finished(self):
        indexes = []
        for i, reminder in enumerate(self.reminder_data):
            if reminder[0] - time.time() < 0:
                indexes.append(i)

        self.remove_reminders(indexes)
