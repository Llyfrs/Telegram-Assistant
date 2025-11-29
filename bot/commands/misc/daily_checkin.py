"""Trigger daily habit check-in manually."""

from bot.classes.command import Command
from bot.watchers.daily_checkin import DailyCheckin
from utils.logging import get_logger

logger = get_logger(__name__)


class Checkin(Command):
    """Manually trigger the daily habit check-in"""
    
    command_name = "daily_checkin"
    
    @classmethod
    async def handle(cls, update, context):
        """Trigger the daily check-in job."""
        logger.info("Manual daily check-in triggered by user")
        
        try:
            await DailyCheckin.job(context)
            await update.message.reply_text("✅ Daily check-in sent!")
        except Exception as exc:
            logger.error("Error triggering daily check-in: %s", exc)
            await update.message.reply_text(f"❌ Error: {exc}")

