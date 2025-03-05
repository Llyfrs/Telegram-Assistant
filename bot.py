#!/usr/bin/python3

import asyncio
import datetime
import glob
import importlib
import json
import logging
import os

import pytz
from telegram.ext import Defaults

import openai_api
from commands.assistant.assistant import get_current_time
from commands.misc.auth import calendar_auth_handler
from commands.time_table.time_table import time_table_handler
from hacks.CustomeAplicationBuilder import CustomApplicationBuilder
from modules.Settings import Settings
from modules.calendar import Calendar
from modules.database import ValkeyDB
from modules.email import Event
from modules.reminder import Reminders, calculate_seconds, seconds_until
from modules.timetable import TimeTable
from modules.torn import Torn
from modules.wolfamalpha import calculate
from watchers.email_summary import EmailSummary, blocking_add_event

## For commands to be loaded they need to be imported
## You could do it by hand (import commands.command_name)
## You could do it with __init__.py file in commands directory and then just do from commands import *
## But I don't like having to go somewhere after I create command and write it, so I import anything in commands directory including subdirectories
[importlib.import_module(os.path.relpath(f, os.getcwd()).replace(os.path.sep, ".")[:-3]) for f in
 glob.glob("commands/**/*.py", recursive=True) if os.path.basename(f) != "__init__.py"]

## Same as above but for watchers
[importlib.import_module(os.path.relpath(f, os.getcwd()).replace(os.path.sep, ".")[:-3]) for f in
 glob.glob("watchers/**/*.py", recursive=True) if os.path.basename(f) != "__init__.py"]

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

chat_id = None
ct = None

if __name__ == '__main__':

    defaults = Defaults(tzinfo=pytz.timezone('CET'))  ## Makes sure that

    application = (CustomApplicationBuilder()
                   .token(os.environ.get("TELEGRAM_KEY"))
                   .pool_timeout(10)
                   .defaults(defaults)
                   .build()
                   )

    application.bot_data["settings"] = Settings("settings.pickle")

    creds = ValkeyDB().get("callendar_credentials")

    if creds is not None:
        creds = json.loads(creds)

    token = ValkeyDB().get_serialized("calendar_token")

    application.bot_data["calendar"] = Calendar(creds, token)

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

    application.bot_data["reminder"] = reminder
    application.bot_data["timetable"] = TimeTable(pytz.timezone('CET'))

    client.add_function(get_current_time, "get_current_time", "Returns the current time")
    client.add_function(seconds_until, "seconds_until", "Returns seconds until date in format %Y-%m-%d %H:%M:%S")

    client.add_function(calculate_seconds, "convert_to_seconds",
                        "Converts days, hours, minutes and seconds to just seconds")

    client.add_function(reminder.add_reminder, "add_reminder",
                        "Creates reminder that will be send to user after specified time.")

    client.add_function(reminder.remove_reminders, "cancel_reminder", "Cancels reminders.")
    client.add_function(reminder.get_reminders, "get_reminders", "Returns list of all running reminders")

    client.add_function(blocking_add_event, "create_event", "Creates event in a calendar. "
                                                            "Should be use for any approaching events that the user "
                                                            "should be aware of continuously")

    client.create()

    application.bot_data["client"] = client

    logging.info(client.functions.get_list_of_functions())

    application.run_polling()
