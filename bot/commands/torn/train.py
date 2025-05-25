from telegram import Update
from telegram.ext import ContextTypes

from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn

@command
async def train(update : Update, context: ContextTypes.DEFAULT_TYPE):
    torn : Torn = context.bot_data[BotData.TORN]
    await torn.trains()
