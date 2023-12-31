#!/usr/bin/python3

import asyncio
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import openai_api
import os
import logging
import datetime
from modules.reminder import Reminders, calculate_seconds
from modules.Settings import Settings
from modules.tools import debug
from modules.wolfamalpha import calculate
from modules.files import load_file, save_file, delete_file, get_sections, get_section, list_files, save_section, add_section, create_file

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

settings = Settings("settings.pickle")

chat_id = None
ct = None


async def toggle_retrieval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Toggles retrieval mode.
    This will enable the retrieval tool and switch mode to GPT4
    """
    settings.set_setting("retrieval", not settings.get_setting("retrieval"))

    await update.message.reply_text(f"Retrieval is now {settings.get_setting('retrieval')}")


async def toggle_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Toggles debug mode """
    settings.set_setting("debug", not settings.get_setting("debug"))
    await update.message.reply_text(f"Debug is now {settings.get_setting('debug')}")


async def toggle_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if client.model == "gpt-4-1106-preview":
        client.set_model("gpt-3.5-turbo-1106")
    else:
        client.set_model("gpt-4-1106-preview")

    await update.message.reply_text(f"Model is now {client.model}")


async def set_wolframalpha_app_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Sets WolframAlpha app id """
    settings.set_setting("wolframalpha_app_id", update.message.text.split(" ")[1])
    await update.message.reply_text(f"WolframAlpha app id set to {settings.get_setting('wolframalpha_app_id')}")


async def clear_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Clears the thread """
    client.clear_thread()
    await update.message.reply_text(f"Thread cleared")


async def assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminder.chat_id = update.effective_chat.id

    client.add_message(update.message.text)
    steps = client.run_assistant()

    if settings.get_setting("debug"):
        for dbg_msg in debug(steps):

            print(dbg_msg)
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
                await context.bot.send_message(chat_id=update.effective_chat.id, text=content.text.value)

            if content.type == "image_file":
                content = client.client.files.content(file_id=content.image_file.file_id)
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=content)


def get_current_time():
    # TODO: Show local time and don't show seconds as float
    current_time_and_date = datetime.datetime.now()
    current_time_and_date = current_time_and_date.strftime("%H:%M:%S %d/%m/%Y")

    print("Returning time: " + str(current_time_and_date))
    return {"current_time": current_time_and_date}


async def load_commands():
    await telegram.Bot.set_my_commands(application.bot, [
        ("toggle_retrieval", "Toggles retrieval mode"),
        ("toggle_debug", "Toggles debug mode"),
        ("clear_thread", "Clears the thread"),
        ("toggle_model", "Toggles model between GPT4 and GPT3.5"),
        ("set_wolframalpha_app_id", "Sets WolframAlpha app id")
    ])


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_KEY")).pool_timeout(10).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, assistant))
    application.add_handler(CommandHandler("toggle_retrieval", toggle_retrieval))
    application.add_handler(CommandHandler("toggle_debug", toggle_debug))
    application.add_handler(CommandHandler("clear_thread", clear_thread))
    application.add_handler(CommandHandler("toggle_model", toggle_model))
    application.add_handler(CommandHandler("set_wolframalpha_app_id", set_wolframalpha_app_id))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_commands())
    # model = "gpt-4-1106-preview"
    model = "gpt-3.5-turbo-1106"
    client = openai_api.OpenAI_API(os.environ.get("OPENAI_KEY"), model)
    reminder = Reminders(application.bot)

    client.add_function(get_current_time, "get_current_time", "Returns the current time")
    client.add_function(calculate, "calculate", "Calculates math expression using wolframalpha. Can also calculate dates for example")
    client.add_function(calculate_seconds, "calculate_seconds",
                        "Calculates seconds from days, hours, minutes and seconds. Use to get seconds for reminder. "
                        "Does not tell time until.")
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

    print(client.functions.get_list_of_functions())

    application.run_polling()
