import logging

from telegram.ext import ContextTypes
from bot.classes.watcher import run_repeated
from enums.bot_data import BotData
from modules.torn import Torn, remove_between_angle_brackets


# TODO: Loogging
@run_repeated(interval=30)
async def torn_new_events(context: ContextTypes.DEFAULT_TYPE):

    ## Inits static variable
    if not hasattr(torn_new_events, "oldest_event"):
        torn_new_events.oldest_event = 0

    torn : Torn = context.bot_data.get(BotData.TORN)

    user = await torn.get_user()

    newevents = user.get("events")

    events = []

    for event_id in newevents:
        if newevents[event_id].get("timestamp") > torn_new_events.oldest_event:
            torn_new_events.oldest_event = newevents[event_id].get("timestamp")
            events.append(remove_between_angle_brackets(newevents[event_id].get("event")))

    if len(events) > 0:
        logging.info("New event found, sending alert")
        await torn.send("*Events*\n\n" + "\n".join(events), clean=False)

    pass