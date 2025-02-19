import asyncio

from commands.command import command
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