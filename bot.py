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
    client.run_assistant()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=client.get_last_message())


def get_current_time(dummy):
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
    client.add_function(reminder.add_reminder, "add_reminder", "Adds a reminder to the reminder list")

    client.create()

    print(client.functions.get_list_of_functions())



    application.run_polling()
