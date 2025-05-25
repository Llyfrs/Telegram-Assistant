from bot.classes.command import command
from enums.bot_data import BotData


@command
async def clear_thread(update, context):
    """ Clears the thread """
    context.bot_data[BotData.MESSAGE_HISTORY] = []
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Thread cleared."
    )