"""Daily check-in watcher for habit tracking."""

from datetime import time

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, ContextTypes, CallbackQueryHandler

from bot.classes.watcher import Watcher
from enums.database import DatabaseConstants
from modules.database import MongoDB
from modules.habits import get_active_habits, update_daily_log, get_habit_by_id
from utils.logging import get_logger

logger = get_logger(__name__)


class DailyCheckin(Watcher):
    """Send daily check-in forms for habit tracking."""

    # Default check-in time: 9 PM
    checkin_hour = 19
    checkin_minute = 10

    @classmethod
    def setup(cls, app: Application) -> None:
        """Schedule the daily check-in and register callback handlers."""
        logger.info("Setting up DailyCheckin watcher")

        if app.job_queue is None:
            raise ValueError("Application instance does not have a job queue.")

        # Schedule daily job
        app.job_queue.run_daily(
            cls.job,
            time=time(hour=cls.checkin_hour, minute=cls.checkin_minute),
        )

        # Register callback handler for habit responses
        app.add_handler(CallbackQueryHandler(cls.handle_habit_response, pattern=r"^habit:"))

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send daily check-in messages."""
        if not MongoDB().get("notify_daily_habit_checkin", False):
            return

        chat_id = MongoDB().get(DatabaseConstants.MAIN_CHAT_ID)

        if chat_id is None:
            logger.warning("MAIN_CHAT_ID not set, skipping daily check-in")
            return

        if isinstance(chat_id, str):
            chat_id = int(chat_id)

        # Get active habits
        habits = get_active_habits()

        if not habits:
            logger.info("No habits to check in for chat %s", chat_id)
            return

        logger.info("Sending daily check-in for %d habits to chat %s", len(habits), chat_id)

        # Send habit check-in messages (all at once)
        for habit in habits:
            await cls.send_habit_checkin(context, chat_id, habit)

    @classmethod
    async def send_habit_checkin(cls, context: ContextTypes.DEFAULT_TYPE, chat_id: int, habit) -> None:
        """Send a check-in message for a single habit."""
        
        if habit.habit_type == "boolean":
            keyboard = [
                [
                    InlineKeyboardButton("Yes ✓", callback_data=f"habit:{habit.habit_id}:yes"),
                    InlineKeyboardButton("No ✗", callback_data=f"habit:{habit.habit_id}:no"),
                ]
            ]
            prompt = "Did you do it today?"
        else:
            # Count type - use custom options
            options = habit.options or ["0", "1", "2", "3", "4+"]
            buttons = [
                InlineKeyboardButton(opt, callback_data=f"habit:{habit.habit_id}:{opt}")
                for opt in options
            ]
            # Split into rows of 5 max
            keyboard = [buttons[i:i+5] for i in range(0, len(buttons), 5)]
            prompt = "How did it go today?"

        # Pick emoji based on color
        color_emojis = {
            "green": "🌿",
            "blue": "💙",
            "purple": "💜",
            "orange": "🧡",
            "red": "❤️",
            "cyan": "💎",
            "pink": "🩷",
        }
        emoji = color_emojis.get(habit.color, "📋")

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{emoji} *{habit.name}* — {prompt}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    @classmethod
    async def handle_habit_response(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle habit check-in button press."""
        query = update.callback_query
        await query.answer()

        # Parse callback data: habit:{habit_id}:{value}
        parts = query.data.split(":")
        if len(parts) != 3:
            logger.error("Invalid habit callback data: %s", query.data)
            return

        _, habit_id, value = parts
        chat_id = query.message.chat.id

        # Update the daily log
        update_daily_log(habit_id=habit_id, habit_value=value)

        # Get habit for confirmation message
        habit = get_habit_by_id(habit_id)
        habit_name = habit.name if habit else "Habit"

        # Pick emoji based on color
        color_emojis = {
            "green": "🌿",
            "blue": "💙",
            "purple": "💜",
            "orange": "🧡",
            "red": "❤️",
            "cyan": "💎",
            "pink": "🩷",
        }
        emoji = color_emojis.get(habit.color if habit else "green", "📋")

        # Update message to show recorded value
        if habit and habit.habit_type == "boolean":
            if value.lower() in ("yes", "true", "1"):
                response_text = f"✅ *{habit_name}* — Recorded: Yes"
            else:
                response_text = f"❌ *{habit_name}* — Recorded: No"
        else:
            response_text = f"{emoji} *{habit_name}* — Recorded: {value}"

        await query.edit_message_text(
            text=response_text,
            parse_mode="Markdown",
        )

        logger.info("Recorded habit %s = %s for chat %s", habit_id, value, chat_id)
