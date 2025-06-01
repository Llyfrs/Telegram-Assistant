from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import ValkeyDB
from modules.torn import Torn


@run_repeated(interval=30)
async def torn_hospital(context: ContextTypes.DEFAULT_TYPE):
    """
    Checks if the user is in the hospital. If not notifies them.
    (this is for competition and mostly useless otherwise)
    """

    torn : Torn = context.bot_data.get(BotData.TORN)
    user = await torn.get_user()

    if user is None:
        return

    if user["status"]["state"] != "Hospital":
        await context.bot.send_message(
            chat_id=ValkeyDB().get_serialized(DatabaseConstants.MAIN_CHAT_ID),
            text="You are not in the hospital. Please walk in to some doors. https://www.torn.com/gym.php"
        )