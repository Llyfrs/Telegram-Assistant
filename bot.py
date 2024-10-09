#!/usr/bin/python3

import asyncio
import datetime
import logging
import os
import time
from asyncio import Future

import pytz
import telegram
import telegramify_markdown
from anyio import current_time
from telebot.types import InlineQuery
from telegram import Update, Message, helpers, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from conversations.time_table_creation import time_table_handler
from modules.database import ValkeyDB

import openai_api
from modules.Settings import Settings
from modules.reminder import Reminders, calculate_seconds, convert_seconds_to_hms, seconds_until
from modules.timetable import TimeTable
from modules.tools import debug
from modules.torn import Torn
from modules.wolfamalpha import calculate
from modules.files import load_file, save_file, delete_file, get_sections, get_section, list_files, save_section, \
    add_section, create_file


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

async def toggle_retrieval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Toggles retrieval mode.
    This will enable the retrieval tool and switch mode to GPT4
    """
    db = ValkeyDB()
    db.set_serialized("retrieval", not db.get_serialized("retrieval", False))
    await update.message.reply_text(f"Retrieval is now: {db.get_serialized('retrieval')}")


async def toggle_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Toggles debug mode """
    db = ValkeyDB()
    db.set_serialized("debug", not db.get_serialized("debug", False))
    await update.message.reply_text(f"Debug is now: {db.get_serialized('debug')}")


async def toggle_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if client.model == "gpt-4o":
        client.set_model("gpt-4o-mini")
    else:
        client.set_model("gpt-4o")

    await update.message.reply_text(f"Model is now {client.model}")


async def set_wolframalpha_app_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Sets WolframAlpha app id """
    db = ValkeyDB()
    db.set_serialized("wolframalpha_app_id", update.message.text.split(" ")[1])
    await update.message.reply_text(f"WolframAlpha app id set")


async def set_torn_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Sets Torn API key and resets already running torn instance so only one is running"""
    db = ValkeyDB()
    db.set_serialized("torn_api_key", update.message.text.split(" ")[1])
    db.set_serialized("chat_id", update.message.chat.id)

    torn = context.bot_data["torn"]
    torn.cancel()

    torn = Torn(application.bot, ValkeyDB().get_serialized("torn_api_key", ""), ValkeyDB().get_serialized("chat_id"))
    asyncio.run_coroutine_threadsafe(torn.run(), loop)

    await update.message.reply_text(f"Torn API key set")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    torn = context.bot_data["torn"]
    await torn.stock()

async def stacking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    torn = context.bot_data["torn"]
    torn.set_stacking(not torn.get_stacking())
    await update.message.reply_text(f"Stacking is now: {torn.get_stacking()}")

async def clear_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Clears the thread """
    client.clear_thread()
    await update.message.reply_text(f"Thread cleared")


async def live_message( update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Live message """
    message : Message = await update.message.reply_text("Live message")


    ## I did tested it in ouside of courutine but for some reason thsese async functions are blocking everything else
    ## I should look in to changing that in the future, there might be option for that or
    ## I can just warp the functions in something that will make them run async
    async def timer():
        start = time.time()
        while True:
            await message.edit_text(convert_seconds_to_hms(round(time.time() - start)))
            await asyncio.sleep(1)

    loop = asyncio.get_running_loop()
    asyncio.run_coroutine_threadsafe(timer(), loop)

async def bounty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Bounty """

    try:

        bt : Future = context.bot_data.get("bounty", None)

        if bt is not None:
            bt.cancel()
            context.bot_data["bounty"] = None
            await update.message.reply_text("Bounty Monitor Stoped")
            return

        torn = context.bot_data["torn"]
        loop = asyncio.get_running_loop()
        bt = asyncio.run_coroutine_threadsafe(torn.bounty_monitor(), loop)
        context.bot_data["bounty"] = bt


    except Exception as ex:
        logging.error(f"Failed to get bounties {ex}")

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timetable = context.bot_data["timetable"]

    lesson = timetable.next()

    if lesson is None:
        await update.message.reply_text("No more lessons today")
        return

    reply = f"*{lesson['course']}*\n " \
            f"time: {lesson['start']}-{lesson['end']} " \
            f"location: {lesson['location']}"

    reply = telegramify_markdown.markdownify(reply)

    await update.message.reply_text(reply, parse_mode="MarkdownV2")

    pass


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timetable = context.bot_data["timetable"]

    lesson = timetable.now()

    if lesson is None:
        await update.message.reply_text("No more lessons today")
        return

    reply = f"*{lesson['course']}*\n " \
            f"time: {lesson['start']}-{lesson['end']} " \
            f"location: {lesson['location']}"

    reply = telegramify_markdown.markdownify(reply)

    await update.message.reply_text(reply, parse_mode="MarkdownV2")

    pass

async def assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminder.chat_id = update.effective_chat.id

    ## Change status to typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")


    photos = []
    photo = update.message.photo
    for p in photo:
        photo = await context.bot.get_file(p.file_id)
        photos.append(photo.file_path)


    ## Looks like it duplicates the photos, this should make sure it doesn't do that anymore
    photos = set(photos)
    client.add_message( f"{get_current_time()["current_time"]}: {update.message.text}", photos)

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


# NOTE: it is actually possible to update commands only for specific chat, interesting indeed
async def load_commands():
    await telegram.Bot.set_my_commands(application.bot, [
        ("toggle_retrieval", "Toggles retrieval mode"),
        ("toggle_debug", "Toggles debug mode"),
        ("clear_thread", "Clears the thread"),
        ("toggle_model", "Toggles model between GPT4 and GPT4o-mini"),
        ("set_wolframalpha_app_id", "Sets WolframAlpha app id"),
        ("set_torn_api_key", "Sets Torn API key"),
        ("live_message", "Live message"),
        ("stock", "Stock"),
        ("stacking", "Toggles stacking mode, preventing notifications for full energy bar"),
        ("get_link", "Returns link to the bot"),
        ("bounty", "Starts bounty monitor")
    ])



if __name__ == '__main__':
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_KEY")).pool_timeout(10).build()

    application.bot_data["settings"] = Settings("settings.pickle")

    application.add_handler(time_table_handler())

    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, assistant))
    application.add_handler(CommandHandler("toggle_retrieval", toggle_retrieval))
    application.add_handler(CommandHandler("toggle_debug", toggle_debug))
    application.add_handler(CommandHandler("clear_thread", clear_thread))
    application.add_handler(CommandHandler("toggle_model", toggle_model))
    application.add_handler(CommandHandler("set_wolframalpha_app_id", set_wolframalpha_app_id))
    application.add_handler(CommandHandler("set_torn_api_key", set_torn_api_key))
    application.add_handler(CommandHandler("live_message", live_message))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("stacking", stacking))
    application.add_handler(CommandHandler("get_link", get_link))
    application.add_handler(CommandHandler("bounty", bounty))
    application.add_handler(CommandHandler("set_timezone", set_timezone))
    application.add_handler(CommandHandler("next", next))
    application.add_handler(CommandHandler("now", now))



    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_commands())

    t = Torn(application.bot, ValkeyDB().get_serialized("torn_api_key", ""), ValkeyDB().get_serialized("chat_id"))
    application.bot_data["torn"] = t

    asyncio.run_coroutine_threadsafe(t.run(), loop)

    # model = "gpt-4-1106-preview"
    model = "gpt-4o-mini"
    client = openai_api.OpenAI_API(os.environ.get("OPENAI_KEY"), model)

    reminder = Reminders(application.bot)


    application.bot_data["timetable"] = TimeTable(pytz.timezone('CET'))

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

    logging.info(client.functions.get_list_of_functions())

    application.run_polling()
