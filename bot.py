#!/usr/bin/python3

import asyncio
import datetime
import json
import logging

import pytz
import telegramify_markdown
from telebot.types import Update
from telegram import helpers
from telegram.ext import ContextTypes, MessageHandler, filters

import openai_api
from commands.auth import calendar_auth_handler
from commands.time_table.time_table import time_table_handler
from hacks.CustomeAplicationBuilder import CustomApplicationBuilder
from modules.Settings import Settings
from modules.calendar import Calendar
from modules.database import ValkeyDB
from modules.email import email_updates
from modules.files import load_file, save_file, delete_file, get_sections, get_section, list_files, save_section, \
    add_section, create_file
from modules.reminder import Reminders, calculate_seconds, seconds_until
from modules.timetable import TimeTable
from modules.tools import debug
from modules.torn import Torn
from modules.wolfamalpha import calculate

## For commands to be loaded they need to be imported
## You could do it by hand (import commands.command_name)
## You could do it with __init__.py file in commands directory and then just do from commands import *
## But I don't like having to go somewhere after I create command and write it, so I import anything in commands directory including subdirectories
import importlib, glob, os; [importlib.import_module(os.path.relpath(f, os.getcwd()).replace(os.path.sep, ".")[:-3]) for f in glob.glob("commands/**/*.py", recursive=True) if os.path.basename(f) != "__init__.py"]

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

chat_id = None
ct = None

costs = {
    "gpt-4o": 0.00500 / 1000,
    "gpt-4o-mini": 0.000150 / 1000,
}

## Interesting concept, for adding controls right in to messages
## Unfortunately it seems to only call the start function and needs to be used with
## application.add_handler(CommandHandler("start", deep_linked_level_4, filters.Regex(USING_KEYBOARD)))
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = helpers.create_deep_linked_url(context.bot.username , "test")
    await update.message.reply_text(url)

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminder.chat_id = update.effective_chat.id

    ## Change status to typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    print(update)

    photos = []
    if len(update.message.photo):
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)# Renamed to clarify
        photos.append(file.file_path)

    message = update.message.text

    if len(photos) != 0:
        logging.info(f"User sent {len(photos)} photos")
        message = update.message.caption

    client.add_message( f"{get_current_time()['current_time']}: {message}", photos)

    steps = client.run_assistant()

    db = ValkeyDB()

    if db.get_serialized("debug", False):

        cost = client.last_run_cost
        dollar_cost = costs[client.model] * cost.total_tokens

        long_time_cost = db.get_serialized("cost", 0)
        if long_time_cost is None:
            long_time_cost = 0

        db.set_serialized("cost", long_time_cost + dollar_cost)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{cost.total_tokens} tokens used for price of ${round(dollar_cost,5)}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Total cost: ${round(long_time_cost + dollar_cost, 5)}")

        for dbg_msg in debug(steps):

            logging.info(dbg_msg)
            # TODO this need to be fixed ffs it's so ugly
            if dbg_msg == "":
                continue

            await context.bot.send_message(chat_id=update.effective_chat.id, text=dbg_msg, parse_mode="MarkdownV2")

    # Sometimes the run is finished but the new message didn't arrive yet
    # so this will make sure we won't miss it
    messages = client.get_new_messages()
    while len(messages.data) == 0:
        messages = client.get_new_messages()
        return

    for message in messages:
        for content in message.content:
            if content.type == "text":

                await context.bot.send_message(chat_id=update.effective_chat.id, text=telegramify_markdown.markdownify(content.text.value), parse_mode="MarkdownV2")

            if content.type == "image_file":
                content = client.client.files.content(file_id=content.image_file.file_id)
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=content)


def get_current_time():

    cet = pytz.timezone('CET')
    current_time_and_date = datetime.datetime.now(cet)
    current_time_and_date = current_time_and_date.strftime("%H:%M:%S %d/%m/%Y")

    print("Returning time: " + str(current_time_and_date))
    return {"current_time": current_time_and_date}




if __name__ == '__main__':
    application = CustomApplicationBuilder().token(os.environ.get("TELEGRAM_KEY")).pool_timeout(10).build()

    application.bot_data["settings"] = Settings("settings.pickle")

    creds = json.loads(ValkeyDB().get("callendar_credentials"))
    application.bot_data["calendar"] = Calendar(creds)

    application.add_handler(time_table_handler())
    application.add_handler(calendar_auth_handler())

    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, assistant))

    ## loop = asyncio.get_event_loop()
    ## loop.run_until_complete(load_commands())

    chat_id = ValkeyDB().get_serialized("chat_id")

    t = Torn(application.bot, ValkeyDB().get_serialized("torn_api_key", ""), chat_id)
    application.bot_data["torn"] = t

    loop = asyncio.get_event_loop()

    asyncio.run_coroutine_threadsafe(t.run(), loop)

    # model = "gpt-4-1106-preview"
    model = "gpt-4o-mini"
    client = openai_api.OpenAI_API(os.environ.get("OPENAI_KEY"), model)

    reminder = Reminders(application.bot)


    application.bot_data["timetable"] = TimeTable(pytz.timezone('CET'))

    asyncio.run_coroutine_threadsafe(email_updates(application.bot, chat_id), loop)

    client.add_function(get_current_time, "get_current_time", "Returns the current time")
    client.add_function(seconds_until, "seconds_until", "Returns seconds until date in format %Y-%m-%d %H:%M:%S")
    client.add_function(calculate, "calculate",
                        "Calculates math expression using wolframalpha. Can also calculate dates for example")
    client.add_function(calculate_seconds, "convert_to_seconds",
                        "Converts days, hours, minutes and seconds to just seconds")
    client.add_function(reminder.add_reminder, "add_reminder",
                        "Creates reminder that will be send to user after specified time. t"
                        "he time does not accumulate with ever function call.")
    client.add_function(reminder.remove_reminders, "cancel_reminder", "Cancels reminders.")
    client.add_function(reminder.get_reminders, "get_reminders", "Returns list of all running reminders")
    client.add_function(load_file, "load_file", "Loads file from files directory")
    client.add_function(save_file, "save_file", "Saves file to files directory. Does not create a new file")
    client.add_function(delete_file, "delete_file", "Deletes file from files directory")
    client.add_function(get_sections, "get_sections", "Returns list of sections in markdown file")
    client.add_function(get_section, "get_section", "Returns section from markdown file. User does not see the output")
    client.add_function(list_files, "list_files", "Returns list of files in files directory")
    client.add_function(save_section, "save_section", "Saves section to markdown file, (Overrides the existing one)")
    client.add_function(add_section, "add_section", "Adds section to markdown file at its end")
    client.add_function(create_file, "create_file", "Creates file in files directory")


    client.create()

    application.bot_data["client"] = client

    logging.info(client.functions.get_list_of_functions())

    application.run_polling()
