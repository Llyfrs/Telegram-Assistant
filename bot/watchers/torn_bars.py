from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from modules.database import MongoDB
from modules.torn import Torn

@run_repeated(interval=90)
async def torn_racing(context: ContextTypes.DEFAULT_TYPE):

    torn : Torn = context.bot_data.get(BotData.TORN)
    user = await torn.get_user()

    energy = user.get("energy")
    nerve = user.get("nerve")

    head = "Bars Alert"
    message = head

    if user.get("status").get("state") in ["Abroad", "Traveling"]:
        return

    db = MongoDB()

    if energy.get("current") == energy.get("maximum") and not torn.is_stacking:
        if db.get("notify_energy_full", False):
            message += f"\n> Your energy is *full*, use it at [gym](https://www.torn.com/gym.php) 💚"
    elif energy.get("current") > energy.get("maximum") * 0.9 and not torn.is_stacking:
        if db.get("notify_energy_almost_full", False):
            message += f"\n> Your energy is almost full, use it at [gym](https://www.torn.com/gym.php) 💚"

    if nerve.get("current") == nerve.get("maximum"):
        if db.get("notify_nerve_full", False):
            message += f"\n> Your nerve is *full*, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"
    elif nerve.get("current") > nerve.get("maximum") * 0.9:
        if db.get("notify_nerve_almost_full", False):
            message += f"\n> Your nerve is almost full, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"

    if message != head:
        await torn.send(message)
    else:
        await torn.clear()