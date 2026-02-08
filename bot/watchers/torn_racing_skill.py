from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import MongoDB, Document
from modules.torn import Torn
from utils.logging import get_logger

logger = get_logger(__name__)


class RacingSkillRecord(Document):
    """Document model for tracking racing skill history."""

    model_config = ConfigDict(collection_name="racing_skill_history")

    skill: float
    recorded_at: datetime
    gain: Optional[float] = None  # Skill gained in this record (None for initial)


@run_repeated(interval=60)
async def torn_racing_skill(context: ContextTypes.DEFAULT_TYPE):
    """
    Tracks racing skill changes and notifies the user when skill increases.
    Runs every minute and stores skill history in the database.
    """

    db = MongoDB()

    if not db.get("notify_racing_skill", False):
        return

    torn: Torn = context.bot_data.get(BotData.TORN)

    if torn is None:
        return

    user = await torn.get_user()

    if user is None:
        return

    current_skill = user.get("racing")

    if current_skill is None:
        logger.debug("Racing skill not found in user data")
        return

    # API returns racing as string, convert to float
    current_skill = float(current_skill)

    # Get the latest recorded skill from database
    records = RacingSkillRecord.find()
    latest_record = max(records, key=lambda r: r.recorded_at) if records else None

    if latest_record is None:
        # First time tracking - just record the initial value
        RacingSkillRecord(
            skill=current_skill,
            recorded_at=datetime.utcnow()
        ).save()
        logger.info("Initial racing skill recorded: %s", current_skill)
        return

    # Check if skill has increased
    if current_skill > latest_record.skill:
        gain = current_skill - latest_record.skill

        # Record the new value with gain
        RacingSkillRecord(
            skill=current_skill,
            recorded_at=datetime.utcnow(),
            gain=gain
        ).save()

        # Notify the user
        message = (
            f"🏎️ **Racing Skill Increased!**\n"
            f"> Gained: **+{gain:.4f}**\n"
            f"> Current skill: **{current_skill:.4f}**"
        )

        await context.bot.send_message(
            chat_id=db.get(DatabaseConstants.MAIN_CHAT_ID),
            text=message,
            parse_mode="Markdown"
        )

        logger.info("Racing skill increased by %s to %s", gain, current_skill)

