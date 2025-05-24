from telegram import Update
from telegram.ext import ContextTypes

from bot.classes.command import command
from modules.torn import Torn

@command
async def train(update : Update, context: ContextTypes.DEFAULT_TYPE):
    torn : Torn = context.bot_data["torn"]
    await torn.trains()
