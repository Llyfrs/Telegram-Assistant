"""
Creates a self updating message that lists all the available bounties in Torn.
"""

import asyncio
import logging
from typing import Optional

from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn_tasks import bounty_monitor


@command
async def bounty(update, context):
    """Toggle the bounty monitor."""

    try:
        task: Optional[asyncio.Task] = context.bot_data.get("bounty")

        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            context.bot_data["bounty"] = None
            await update.message.reply_text("Bounty Monitor Stopped")
            return

        torn = context.bot_data[BotData.TORN]
        task = context.application.create_task(bounty_monitor(torn))
        context.bot_data["bounty"] = task
        await update.message.reply_text("Bounty Monitor Started")

    except Exception as ex:
        logging.error(f"Failed to get bounties {ex}")