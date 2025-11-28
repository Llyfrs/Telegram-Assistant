#!/usr/bin/python3

import glob
import importlib
import logging
import os

from dotenv import load_dotenv

load_dotenv()

import pytz
from telegram.ext import Defaults

from agents.main_agent import initialize_main_agent
from bot.classes.CustomeAplicationBuilder import CustomApplicationBuilder
from enums.database import DatabaseConstants
from modules.calendar import Calendar
from modules.database import ValkeyDB
from modules.location_manager import LocationManager
from modules.memory import Memory

from modules.timetable import TimeTable
from modules.tools import init_file_manager
from modules.torn import Torn
from enums.bot_data import BotData



## For commands to be loaded they need to be imported
## You could do it by hand (import commands.command_name)
## You could do it with __init__.py file in commands directory and then just do from commands import *
## But I don't like having to go somewhere after I create command and write it, so I import anything in commands directory including subdirectories
[importlib.import_module(os.path.relpath(f, os.getcwd()).replace(os.path.sep, ".")[:-3]) for f in
 glob.glob("bot/**/*.py", recursive=True) if os.path.basename(f) != "__init__.py"]

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

    application.bot_data[BotData.CALENDAR] = Calendar("service_account.json", calendar_id=os.environ.get("CALENDAR_ID"))

    ## loop = asyncio.get_event_loop()
    ## loop.run_until_complete(load_commands())

    application.bot_data[BotData.LOCATION] = LocationManager(history_size=7)

    application.bot_data[BotData.FILE_MANAGER] = init_file_manager()



    chat_id = ValkeyDB().get_serialized(DatabaseConstants.MAIN_CHAT_ID, None)

    API_KEY = ValkeyDB().get_serialized(DatabaseConstants.TORN_API_KEY, "")

    t = Torn(application.bot, API_KEY , chat_id)

    application.bot_data[BotData.TORN] = t

    application.bot_data[BotData.TIMETABLE] = TimeTable(pytz.timezone('CET'))


    application.bot_data[BotData.MEMORY] = Memory(
        user_id="user",
        api_key=os.environ.get('ZEP_API_KEY'),
        first_name="User"
    )

    initialize_main_agent(application)

    application.run_polling()
