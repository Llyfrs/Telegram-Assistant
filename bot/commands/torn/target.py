import time
from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn
from utils.logging import get_logger

logger = get_logger(__name__)

# Dictionary to store recently sent targets with timestamps
recently_sent_targets = {}

@command
async def target(update, context):
    """Get Target out of hospital from your Targeting List."""
    torn: Torn = context.bot_data[BotData.TORN]
    now = int(time.time())

    best_upcoming_target = None
    min_until = float('inf')

    for offset in range(0, 1000, 50):
        logger.debug("Fetching targets with offset %s", offset)
        targets_resp = await torn.get_targeteds(offset=offset)
        targets = targets_resp.get("list", [])

        if not targets:
            if offset == 0:
                await update.message.reply_text("You have no targets in your Targeting List.")
            break

        for target_data in targets:
            target_id = target_data.get("id")
            target_name = target_data.get("name", "Unknown")
            target_status = target_data.get("status", {}).get("state", "Unknown")
            last_action_status = target_data.get("last_action", {}).get("status", "Unknown")  ## Offline, Online, Idle
            until = target_data.get("status", {}).get("until", 0)

            # Skip if target was sent less than 60 seconds ago
            last_sent = recently_sent_targets.get(target_id)
            if last_sent and (now - last_sent < 60):
                continue

            # Check if target is out of hospital and offline
            if target_status.lower() != "hospital" and last_action_status.lower() == "offline":
                await update.message.reply_text(
                    f"Target {target_name} (ID: {target_id}) is not in hospital and is offline. "
                    f"https://www.torn.com/loader.php?sid=attack&user2ID={target_id}"
                )
                recently_sent_targets[target_id] = now
                return

            # Track the target that leaves hospital first
            if target_status.lower() == "hospital" and until > now:
                if until < min_until:
                    min_until = until
                    best_upcoming_target = target_data

    if best_upcoming_target:
        target_id = best_upcoming_target.get("id")
        target_name = best_upcoming_target.get("name", "Unknown")
        wait_seconds = min_until - now
        minutes_left = wait_seconds // 60
        seconds_left = wait_seconds % 60

        await update.message.reply_text(
            f"No offline targets currently out of hospital. "
            f"Next target leaving hospital: {target_name} (ID: {target_id}) in {minutes_left}m {seconds_left}s. "
            f"https://www.torn.com/loader.php?sid=attack&user2ID={target_id}"
        )
        recently_sent_targets[target_id] = now
    else:
        await update.message.reply_text("No suitable offline or upcoming hospital targets found.")

