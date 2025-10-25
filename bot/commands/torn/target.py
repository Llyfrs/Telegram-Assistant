import time
from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn

# Dictionary to store recently sent targets with timestamps
recently_sent_targets = {}

@command
async def target(update, context):
    """Get Target out of hospital from your Targeting List."""
    torn: Torn = context.bot_data[BotData.TORN]
    now = time.time()

    for offset in range(0, 1000, 50):
        targets = await torn.get_targeteds(offset=offset)
        targets = targets.get("list", [])

        if not targets:
            await update.message.reply_text("You have no targets in your Targeting List.")
            break

        for target in targets:
            target_id = target.get("id")
            target_name = target.get("name", "Unknown")
            target_status = target.get("status", {}).get("state", "Unknown")

            # Skip if target was sent less than 60 seconds ago
            last_sent = recently_sent_targets.get(target_id)
            if last_sent and (now - last_sent < 60):
                continue

            if target_status.lower() != "hospital":
                await update.message.reply_text(
                    f"Target {target_name} (ID: {target_id}) is not in hospital. "
                    f"https://www.torn.com/loader.php?sid=attack&user2ID={target_id}"
                )
                recently_sent_targets[target_id] = now
                return
