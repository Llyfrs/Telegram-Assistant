from bot.classes.command import command
from enums.bot_data import BotData
from modules.memory import Memory


@command
async def clear_thread(update, context):
    """ Clears the thread """
    main_agent = context.bot_data[BotData.MAIN_AGENT]
    main_agent.clear_history()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Thread cleared."
    )

    memory: Memory | None = context.bot_data.get(BotData.MEMORY, None)
    if memory:
        memory.clear_memory()