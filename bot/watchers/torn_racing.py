from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import ValkeyDB
from modules.torn import Torn


# icon17

@run_repeated(interval=30)
async def torn_racing(context: ContextTypes.DEFAULT_TYPE):

    """
    Checks if the user is in the hospital. If not notifies them.
    (this is for competition and mostly useless otherwise)
    """

    torn : Torn = context.bot_data.get(BotData.TORN)
    user = await torn.get_user()

    if user is None:
        return

    if user["icons"].get("icon17", None) is None:
        await context.bot.send_message(
            chat_id=ValkeyDB().get_serialized(DatabaseConstants.MAIN_CHAT_ID),
            text="You are not in race. Join now https://www.torn.com/racing.php"
        )