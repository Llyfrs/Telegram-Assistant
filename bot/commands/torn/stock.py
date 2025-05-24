from bot.classes.command import command


@command
async def stock(update, context):
    torn = context.bot_data["torn"]
    await torn.stock()
