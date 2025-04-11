import logging

from telegram.ext import ContextTypes

from modules.calendar import Calendar
from watchers.watcher import run_repeated

logger = logging.getLogger(__name__)

@run_repeated(interval=1800)
async def token_refresher(context: ContextTypes.DEFAULT_TYPE):
    """Refresh the token every hour."""

    calendar : Calendar = context.bot_data["calendar"]

    try:
        result = calendar.is_token_valid()
    except Exception as e:
        result = False
        print(e)

    logger.info(f"Refreshed token: {result}")

