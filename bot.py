#!/usr/bin/python3

import asyncio
import time

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import openai_api
import os
import logging
import datetime
from modules.reminder import Reminders

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

chat_id = None
ct = None


async def assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminder.chat_id = update.effective_chat.id

    client.add_message(update.message.text)
    print(client.run_assistant())

    messages = client.get_new_messages()
    while len(messages.data) == 0:
        messages = client.get_new_messages()
        return

    for message in messages:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message.content[0].text.value)

    # await context.bot.send_message(chat_id=update.effective_chat.id, text=client.get_last_message())


def get_current_time():
    current_time_and_date = datetime.datetime.now()
    print("Returning time:" + str(current_time_and_date))
    return current_time_and_date


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_KEY")).pool_timeout(10).build()

    start_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, assistant)
    application.add_handler(start_handler)

    # model = "gpt-4-1106-preview"
    model = "gpt-3.5-turbo-1106"
    client = openai_api.OpenAI_API(os.environ.get("OPENAI_KEY"), model)
    reminder = Reminders(application.bot)

    client.add_function(get_current_time, "get_current_time", "Returns the current time")
    client.add_function(reminder.add_reminder, "add_reminder", "Creates reminder, use code iterpeter to calculate seconds")
    client.add_function(reminder.remove_reminders, "cancel_reminder", "Cancels reminders.")
    client.add_function(reminder.get_reminders, "get_reminders", "Returns list of all running reminders")

    client.create()

    print(client.functions.get_list_of_functions())

    application.run_polling()
