import asyncio
import pickle
import time
import threading
import logging
from telegram.ext import ContextTypes


class Reminder:
    def __init__(self, seconds: int, chat_id, reminder, bot):
        self.reminder = reminder
        self.chat_id = chat_id
        self.loop = asyncio.get_event_loop()
        self.thread = threading.Timer(seconds, self.run)
        self.thread.start()
        self.bot = bot

    def run(self):
        asyncio.run_coroutine_threadsafe(self.send_reminder(), self.loop)

    async def send_reminder(self):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=self.reminder)
        except Exception as exc:
            print(f"Error sending reminder: {exc}")

    def cancel(self):
        self.thread.cancel()


def convert_seconds_to_hms(seconds: int):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class Reminders:
    def __init__(self, bot):
        self.reminders = []
        self.reminder_data: list = []
        self.chat_id = None
        self.bot = bot

        try:
            with open("reminders.pickle", "rb") as file:
                temp = pickle.load(file)

            for reminder in temp:
                if reminder[0] - time.time() < 0:
                    continue

                self.reminder_data.append(reminder)
                self.reminders.append(Reminder(reminder[0] - time.time(), reminder[2], reminder[1], bot))

        except Exception as exc:
            logging.error(f"Error loading reminders: {exc}")
            pass

    def add_reminder(self, seconds: int, reminder: str = "reminder"):
        rem = Reminder(seconds, self.chat_id, reminder, self.bot)
        self.reminders.append(rem)
        self.reminder_data.append((time.time() + seconds, reminder, self.chat_id))

        with open("reminders.pickle", "wb") as file:
            pickle.dump(self.reminder_data, file)

        logging.info(f"[REMINDER] Reminder set for {convert_seconds_to_hms(seconds)} from now")

        return f"Reminder set for {convert_seconds_to_hms(seconds)} from now"

    def get_reminders(self):

        self.remove_finished()

        logging.info(f"[REMINDER] Getting reminders")

        list_string_data = []
        for i, reminder in enumerate(self.reminder_data):
            list_string_data.append(
                f"{i}: {reminder[1]} finished in {convert_seconds_to_hms(int(reminder[0] - time.time()))}")

        return "\n".join(list_string_data)

    def remove_reminders(self, indexes: list[int]):
        indexes.sort(reverse=True)

        logging.info(f"[REMINDER] Removing reminders {indexes}")

        for index in indexes:
            self.reminders[index].cancel()
            self.reminders.pop(index)
            self.reminder_data.pop(index)

        with open("reminders.pickle", "wb") as file:
            pickle.dump(self.reminder_data, file)

        return "Reminders deleted"

    def remove_finished(self):
        indexes = []
        for i, reminder in enumerate(self.reminder_data):
            if reminder[0] - time.time() < 0:
                indexes.append(i)

        self.remove_reminders(indexes)
