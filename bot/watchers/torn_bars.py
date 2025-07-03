from telegram.ext import ContextTypes

from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from modules.torn import Torn

@run_repeated(interval=30)
async def torn_racing(context: ContextTypes.DEFAULT_TYPE):

    torn : Torn = context.bot_data.get(BotData.TORN)
    user = await torn.get_user()

    energy = user.get("energy")
    nerve = user.get("nerve")

    head = "Bars Alert"
    message = head

    if user.get("status").get("state") in ["Abroad", "Traveling"]:
        return

    if energy.get("current") == energy.get("maximum") and not torn.is_stacking:
        message += f"\n> Your energy is *full*, use it at [gym](https://www.torn.com/gym.php) 💚"
    elif energy.get("current") > energy.get("maximum") * 0.9 and not torn.is_stacking:
        message += f"\n> Your energy is almost full, use it at [gym](https://www.torn.com/gym.php) 💚"

    if nerve.get("current") == nerve.get("maximum"):
        message += f"\n> Your nerve is *full*, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"
    elif nerve.get("current") > nerve.get("maximum") * 0.9:
        message += f"\n> Your nerve is almost full, do some [crime](https://www.torn.com/loader.php?sid=crimes#/) ❤️"

    if message != head:
        await torn.send(message)
    else:
        await torn.clear()