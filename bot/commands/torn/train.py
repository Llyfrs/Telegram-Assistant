from telegram import Update
from telegram.ext import ContextTypes

from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn
from modules.torn_tasks import send_train_status

@command
async def train(update : Update, context: ContextTypes.DEFAULT_TYPE):
    torn : Torn = context.bot_data[BotData.TORN]
    await send_train_status(torn)
