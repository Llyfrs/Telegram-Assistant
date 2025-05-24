import json

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters, Application

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from modules.calendar import Calendar
from modules.database import ValkeyDB

GET_TOKEN = 0

async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    calendar : Calendar = context.bot_data["calendar"]

    auth_url = calendar.get_auth_link()

    await update.message.reply_text(" Click the link to authenticate with google calendar: {}".format(auth_url))

    return GET_TOKEN


async def get_token(update: Update, context: ContextTypes.DEFAULT_TYPE):

    calendar: Calendar = context.bot_data["calendar"]

    code = update.message.text

    token = calendar.exchange_code(code)

    calendar = Calendar(calendar.credentials, token)

    if calendar.is_token_valid():
        context.bot_data["calendar"] = calendar
        ValkeyDB().set_serialized("calendar_token", token)

        await update.message.reply_text("Token is valid and saved")
    else:
        await update.message.reply_text("Token is invalid run /calendar again")


    return ConversationHandler.END


def calendar_auth_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("auth", enter)],
        states={
            GET_TOKEN: [MessageHandler(~filters.COMMAND, get_token)]
        },
        fallbacks=[CommandHandler("cancel", cancel)])


class Auth(Command):

    @classmethod
    def handler(cls, app: Application) -> None:
        app.add_handler(calendar_auth_handler(), group=1)
    pass