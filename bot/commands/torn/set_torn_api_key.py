"""

This command is used to set the Torn API key.
Usage looks like this: /set_torn_api_key <api_key>
This is unfortunately not following the intended way for slash commands. As they are not expected to have parameters.
Should be rewritten into a conversation.

"""

from bot.classes.command import command
from enums.bot_data import BotData
from modules.database import ValkeyDB
from modules.torn import Torn


@command
async def set_torn_api_key(update, context):
    """Sets the Torn API key and refreshes the Torn client instance."""

    db = ValkeyDB()
    parts = update.message.text.split(" ")
    if len(parts) < 2:
        await update.message.reply_text("Usage: /set_torn_api_key <api_key>")
        return

    api_key = parts[1]
    chat_id = update.message.chat.id

    db.set_serialized("torn_api_key", api_key)
    db.set_serialized("chat_id", chat_id)

    torn = Torn(context.bot, api_key, chat_id)
    context.bot_data[BotData.TORN] = torn
    context.application.bot_data[BotData.TORN] = torn

    await update.message.reply_text("Torn API key set")
