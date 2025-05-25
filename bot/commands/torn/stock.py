from bot.classes.command import command
from enums.bot_data import BotData


@command
async def stock(update, context):
    torn = context.bot_data[BotData.TORN]
    await torn.stock()
