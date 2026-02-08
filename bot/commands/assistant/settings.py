from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes, Application

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from modules.database import MongoDB


# Constants for cleaner code
class SettingsState:
    SETTINGS_MENU = 0


class SettingsKey:
    # General
    DEBUG = "debug"
    RETRIEVAL = "retrieval"

    # Torn - Energy & Nerve
    ENERGY_FULL = "notify_energy_full"
    ENERGY_ALMOST_FULL = "notify_energy_almost_full"
    NERVE_FULL = "notify_nerve_full"
    NERVE_ALMOST_FULL = "notify_nerve_almost_full"

    # Torn - Cooldowns
    XANAX_AVAILABLE = "notify_xanax_available"
    BOOSTER_AVAILABLE = "notify_booster_available"

    # Torn - Bounties
    TRACK_BOUNTIES = "track_bounties"

    # Torn - Events
    TORN_EVENTS = "notify_torn_events"

    # Torn - Racing
    RACING_NOTIFICATIONS = "racing_notifications"
    RACING_SKILL_TRACKING = "notify_racing_skill"

    # Torn - Company
    COMPANY_UPDATE = "notify_company_update"
    STOCK_REPORT = "notify_stock_report"
    TRAIN_REPORT = "notify_train_report"
    STOCK_CLEAR = "notify_stock_clear"
    TRAIN_CLEAR = "notify_train_clear"

    # Email
    EMAIL_SUMMARY = "notify_email_summary"

    # Time Capsule
    TIME_CAPSULE = "notify_time_capsule"

    # Habits
    DAILY_HABIT_CHECKIN = "notify_daily_habit_checkin"

    CANCEL = "cancel"
    PAGE_PREFIX = "page:"


# Define all settings with display names, organized into pages for readability
SETTINGS_PAGES = {
    "⚙️ General": [
        ("Debug", SettingsKey.DEBUG),
        ("Retrieval", SettingsKey.RETRIEVAL),
    ],
    "💚 Torn — Energy & Nerve": [
        ("Energy Full Alert", SettingsKey.ENERGY_FULL),
        ("Energy Almost Full Alert", SettingsKey.ENERGY_ALMOST_FULL),
        ("Nerve Full Alert", SettingsKey.NERVE_FULL),
        ("Nerve Almost Full Alert", SettingsKey.NERVE_ALMOST_FULL),
    ],
    "💊 Torn — Cooldowns": [
        ("Xanax Available", SettingsKey.XANAX_AVAILABLE),
        ("Booster Available", SettingsKey.BOOSTER_AVAILABLE),
    ],
    "💰 Torn — Bounties & Events": [
        ("Track Bounties", SettingsKey.TRACK_BOUNTIES),
        ("Torn Events", SettingsKey.TORN_EVENTS),
    ],
    "🏎️ Torn — Racing": [
        ("Racing Join Alert", SettingsKey.RACING_NOTIFICATIONS),
        ("Racing Skill Tracking", SettingsKey.RACING_SKILL_TRACKING),
    ],
    "🏢 Torn — Company": [
        ("Company Update", SettingsKey.COMPANY_UPDATE),
        ("Stock Report", SettingsKey.STOCK_REPORT),
        ("Training Report", SettingsKey.TRAIN_REPORT),
        ("Stock Clear Alert", SettingsKey.STOCK_CLEAR),
        ("Training Clear Alert", SettingsKey.TRAIN_CLEAR),
    ],
    "📨 Other Notifications": [
        ("Email Summary", SettingsKey.EMAIL_SUMMARY),
        ("Time Capsule Delivery", SettingsKey.TIME_CAPSULE),
        ("Daily Habit Check-in", SettingsKey.DAILY_HABIT_CHECKIN),
    ],
}

# Flat list of all settings (for validation)
ALL_SETTINGS = []
for _page_settings in SETTINGS_PAGES.values():
    ALL_SETTINGS.extend(_page_settings)


class SettingsHandler:
    @staticmethod
    def generate_settings_keyboard(page_name: str | None = None):
        """Dynamically generate keyboard based on current settings"""
        db = MongoDB()
        keyboard = []

        if page_name is None:
            # Show page navigation
            for name in SETTINGS_PAGES:
                keyboard.append([InlineKeyboardButton(
                    text=name,
                    callback_data=f"{SettingsKey.PAGE_PREFIX}{name}"
                )])
            keyboard.append([InlineKeyboardButton("Cancel", callback_data=SettingsKey.CANCEL)])
            return InlineKeyboardMarkup(keyboard)

        # Show settings for the selected page
        for display_name, setting_key in SETTINGS_PAGES.get(page_name, []):
            current_value = db.get(setting_key, False)
            status = "✅" if current_value else "❌"
            keyboard.append([InlineKeyboardButton(
                text=f"{status} {display_name}",
                callback_data=setting_key
            )])

        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"{SettingsKey.PAGE_PREFIX}_back")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def start_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Entry point for settings command"""
        context.user_data["settings_page"] = None
        await update.message.reply_text(
            "📋 *Notification Settings*\nSelect a category:",
            parse_mode="Markdown",
            reply_markup=SettingsHandler.generate_settings_keyboard()
        )
        return SettingsState.SETTINGS_MENU

    @staticmethod
    async def handle_setting_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle toggle actions and menu navigation"""
        query = update.callback_query
        await query.answer()

        if query.data == SettingsKey.CANCEL:
            await query.delete_message()
            return ConversationHandler.END

        # Handle page navigation
        if query.data.startswith(SettingsKey.PAGE_PREFIX):
            page = query.data[len(SettingsKey.PAGE_PREFIX):]
            if page == "_back":
                context.user_data["settings_page"] = None
                await query.edit_message_text(
                    "📋 *Notification Settings*\nSelect a category:",
                    parse_mode="Markdown",
                    reply_markup=SettingsHandler.generate_settings_keyboard()
                )
            else:
                context.user_data["settings_page"] = page
                await query.edit_message_text(
                    f"📋 *{page}*\nTap to toggle:",
                    parse_mode="Markdown",
                    reply_markup=SettingsHandler.generate_settings_keyboard(page)
                )
            return SettingsState.SETTINGS_MENU

        # Toggle the setting if it's a valid setting key
        if any(query.data == setting[1] for setting in ALL_SETTINGS):
            db = MongoDB()
            current_value = db.get(query.data, False)
            db.set(query.data, not current_value)

        # Update the message with fresh keyboard on the current page
        current_page = context.user_data.get("settings_page")
        if current_page:
            await query.edit_message_text(
                f"📋 *{current_page}*\nTap to toggle:",
                parse_mode="Markdown",
                reply_markup=SettingsHandler.generate_settings_keyboard(current_page)
            )
        else:
            await query.edit_message_text(
                "📋 *Notification Settings*\nSelect a category:",
                parse_mode="Markdown",
                reply_markup=SettingsHandler.generate_settings_keyboard()
            )
        return SettingsState.SETTINGS_MENU

    @staticmethod
    def get_conversation_handler():
        """Return configured conversation handler"""
        return ConversationHandler(
            entry_points=[CommandHandler("settings", SettingsHandler.start_settings)],
            states={
                SettingsState.SETTINGS_MENU: [
                    CallbackQueryHandler(SettingsHandler.handle_setting_toggle)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            map_to_parent={ConversationHandler.END: -1}
        )


class Settings(Command):
    @classmethod
    def handler(cls, app: Application) -> None:
        app.add_handler(SettingsHandler.get_conversation_handler())