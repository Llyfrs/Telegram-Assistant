import asyncio
import time

from telegram import Message

from bot.classes.command import command
from modules.reminder import convert_seconds_to_hms

@command
async def live_message( update, context):
    """ Live message """
    
    message : Message = await update.message.reply_text("Live message")

    async def timer():
        start = time.time()
        while True:
            await message.edit_text(convert_seconds_to_hms(round(time.time() - start)))
            await asyncio.sleep(1)

    loop = asyncio.get_running_loop()
    asyncio.run_coroutine_threadsafe(timer(), loop)