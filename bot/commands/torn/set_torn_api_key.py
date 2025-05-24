"""

This command is used to set the Torn API key.
Usage looks like this: /set_torn_api_key <api_key>
This is unfortunately is not following the intended way for slash commands. As they are not expected to have parameters.
Should be rewritten in to conversation.

"""

import asyncio

from bot.classes.command import command
from modules.database import ValkeyDB
from modules.torn import Torn


@command
async def set_torn_api_key(update, context):
    """ Sets Torn API key and resets already running torn instance so only one is running """

    db = ValkeyDB()
    db.set_serialized("torn_api_key", update.message.text.split(" ")[1])
    db.set_serialized("chat_id", update.message.chat.id)

    torn = context.bot_data["torn"]
    torn.cancel()

    loop = asyncio.get_event_loop()

    torn = Torn(torn.bot, ValkeyDB().get_serialized("torn_api_key", ""), ValkeyDB().get_serialized("chat_id"))
    asyncio.run_coroutine_threadsafe(torn.run(), loop)

    await update.message.reply_text(f"Torn API key set")
