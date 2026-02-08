from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from modules.database import MongoDB
from modules.torn import Torn

# TODO: Loogging
@run_repeated(interval=180)
async def torn_cooldowns(context: ContextTypes.DEFAULT_TYPE):
    torn : Torn = context.bot_data.get(BotData.TORN)

    user = await torn.get_user()

    cooldowns = user.get("cooldowns")
    status = user.get("status")

    db = MongoDB()

    message = "*Cooldown Alarms*:"
    ## Tell player to use up their cooldowns if they can
    if status.get("state") == "Okay" or status.get("state") == "Hospital":

        if cooldowns.get("drug") == 0 and db.get("notify_xanax_available", False):
             message += "\n >Take Xanax 💊 [here](https://www.torn.com/item.php#drugs-items)"

        # if cooldowns.get("medical") == 0:  # I mean I could turn it on but I don't want
        #     message += "\n > Use blood bag 💉 [here](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=medical)"

        if cooldowns.get("booster") == 0 and db.get("notify_booster_available", False):
            message += "\n > Use boosters 🍺 [here](https://www.torn.com/factions.php?step=your&type=1#/tab=armoury&start=0&sub=boosters)"

    if message != "*Cooldown Alarms*:":
        await torn.send(message)
    else:
        await torn.clear()


    pass