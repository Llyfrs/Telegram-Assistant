from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn_tasks import send_stock_report


@command
async def stock(update, context):
    torn = context.bot_data[BotData.TORN]
    await send_stock_report(torn)
