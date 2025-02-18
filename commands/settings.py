from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes

from modules.database import ValkeyDB
from commands.time_table import cancel

class SettingsEnum:
    DEBUG = "debug"
    RETRIEVAL = "retrieval"


def generate_keyboard():
    db = ValkeyDB()

    keyboard = []

    keyboard.append([ InlineKeyboardButton(text=f"Debug: {db.get_serialized(SettingsEnum.DEBUG)}", callback_data=SettingsEnum.DEBUG)])
    keyboard.append([ InlineKeyboardButton(text=f"Retrieval: {db.get_serialized(SettingsEnum.RETRIEVAL)}", callback_data=SettingsEnum.RETRIEVAL)])

    keyboard.append([InlineKeyboardButton(text="Cancel",callback_data="cancel")])

    return InlineKeyboardMarkup(keyboard)


async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query is not None:
        await query.answer()

        if query.data == SettingsEnum.DEBUG:
            db = ValkeyDB()
            db.set_serialized("debug", not db.get_serialized("debug", False))

        if query.data == SettingsEnum.RETRIEVAL:
            db = ValkeyDB()
            db.set_serialized("retrieval", not db.get_serialized("retrieval", False))

        if query.data == "cancel":
            await query.delete_message()
            return -1

        await query.edit_message_text("Click to toggle settings", reply_markup=generate_keyboard())


    await update.message.reply_text("Click to toggle settings", reply_markup=generate_keyboard())
    return 0


def settings_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("settings", enter)],
        states={
            0: [CallbackQueryHandler(enter)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )