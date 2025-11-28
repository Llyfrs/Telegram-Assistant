from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes, Application

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from modules.database import MongoDB


# Constants for cleaner code
class SettingsState:
    SETTINGS_MENU = 0


class SettingsKey:
    DEBUG = "debug"
    RETRIEVAL = "retrieval"
    CANCEL = "cancel"


# Define all settings and their display names
SETTINGS = [
    ("Debug", SettingsKey.DEBUG),
    ("Retrieval", SettingsKey.RETRIEVAL)
]


class SettingsHandler:
    @staticmethod
    def generate_settings_keyboard():
        """Dynamically generate keyboard based on current settings"""
        db = MongoDB()
        keyboard = []

        for display_name, setting_key in SETTINGS:
            current_value = db.get(setting_key, False)
            keyboard.append([InlineKeyboardButton(
                text=f"{display_name}: {current_value}",
                callback_data=setting_key
            )])

        keyboard.append([InlineKeyboardButton("Cancel", callback_data=SettingsKey.CANCEL)])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def start_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Entry point for settings command"""
        await update.message.reply_text(
            "Click to toggle settings:",
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

        # Toggle the setting if it's a valid setting key
        if any(query.data == setting[1] for setting in SETTINGS):
            db = MongoDB()
            current_value = db.get(query.data, False)
            db.set(query.data, not current_value)

        # Update the message with fresh keyboard
        await query.edit_message_text(
            "Click to toggle settings:",
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