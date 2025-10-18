"""

Toggle for stacking mode in Torn. Changes some behaviour to take into account that the user is intentionally keeping energy above maximum.

"""

from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn

"""
list": [
    {
      "id": 929799,
      "name": "Abs11x",
      "level": 68,
      "faction_id": null,
      "status": {
        "description": "Okay",
        "details": null,
        "state": "Okay",
        "color": "green",
        "until": null
      },
      "last_action": {
        "status": "Offline",
        "timestamp": 1633087676,
        "relative": "1478 days ago"
      }
    },
    
    api format

"""


@command
async def target(update, context):
    """Get Target out of hospital from your Targeting List."""
    torn : Torn = context.bot_data[BotData.TORN]

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

            if target_status.lower() != "hospital":
                await update.message.reply_text(f"Target {target_name} (ID: {target_id}) is not in hospital. https://www.torn.com/loader.php?sid=attack&user2ID={target_id}")
                return

