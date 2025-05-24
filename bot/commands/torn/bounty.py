"""
Creates a self updating message that lists all the available bounties in torn.
See torn.bounty_monitor for more information
"""

import asyncio
import logging
from asyncio import Future

from bot.classes.command import command


@command
async def bounty(update, context):
    """ Bounty """

    try:

        bt : Future = context.bot_data.get("bounty", None)

        if bt is not None:
            bt.cancel()
            context.bot_data["bounty"] = None
            await update.message.reply_text("Bounty Monitor Stopped")
            return

        torn = context.bot_data["torn"]
        loop = asyncio.get_running_loop()
        bt = asyncio.run_coroutine_threadsafe(torn.bounty_monitor(), loop)
        context.bot_data["bounty"] = bt


    except Exception as ex:
        logging.error(f"Failed to get bounties {ex}")