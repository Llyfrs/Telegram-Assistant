from telebot.types import InlineKeyboardButton
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes

from modules.database import ValkeyDB
from time_table import cancel

class SettingsEnum:
    DEBUG = "debug"
    RETRIEVAL = "retrieval"




def generate_keyboard():
    db = ValkeyDB()

    keyboard = []

    keyboard.append([ InlineKeyboardButton(text=f"Debug: {db.get_serialized(SettingsEnum.DEBUG)}", callback_data=SettingsEnum.DEBUG)])
    keyboard.append([ InlineKeyboardButton(text=f"Retrieval: {db.get_serialized(SettingsEnum.RETRIEVAL)}", callback_data=SettingsEnum.RETRIEVAL)])

    return InlineKeyboardMarkup(keyboard)


async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()


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