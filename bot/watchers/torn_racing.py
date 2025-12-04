from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import MongoDB
from modules.torn import Torn

@run_repeated(interval=180)
async def torn_racing(context: ContextTypes.DEFAULT_TYPE):

    """
    Checks if the user is in the hospital. If not notifies them.
    (this is for competition and mostly useless otherwise)
    """

    db = MongoDB()

    # Check if racing notifications are enabled
    if not db.get("racing_notifications", False):
        return

    torn : Torn = context.bot_data.get(BotData.TORN)
    user = await torn.get_user()

    if user is None:
        return

    if user["icons"].get("icon17", None) is None:
        await context.bot.send_message(
            chat_id=db.get(DatabaseConstants.MAIN_CHAT_ID),
            text="You are not in race. Join now https://www.torn.com/racing.php"
        )