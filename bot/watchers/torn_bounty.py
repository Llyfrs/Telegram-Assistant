import logging
from typing import Any, Dict, List, Tuple

from telegram.ext import ContextTypes

from bot.classes.watcher import Watcher
from enums.bot_data import BotData
from modules.torn import Torn
from modules.torn_tasks import get_valid_bounties, watch_player_bounty


class TornBountyWatcher(Watcher):
    interval = 30 * 60

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        torn = context.application.bot_data.get(BotData.TORN)
        if torn is None:
            logging.warning("Torn instance not available for bounty watcher")
            return

        monitor = await get_valid_bounties(torn, 1_000_000)
        if not monitor:
            torn.discovered_bounties = []
            return

        update_discovered: List[Tuple[int, int]] = []
        new_bounties: List[Dict[str, Any]] = []

        for bounty in monitor:
            record = (bounty.get("player_id"), bounty.get("valid_until"))
            if record not in torn.discovered_bounties:
                new_bounties.append(bounty)
            update_discovered.append(record)

        torn.discovered_bounties = update_discovered

        for bounty in new_bounties:
            logging.info(
                "New bounty found: %s with $%s, scheduling watcher",
                bounty.get('name'),
                bounty.get('reward')
            )
            context.application.create_task(watch_player_bounty(torn, bounty))
