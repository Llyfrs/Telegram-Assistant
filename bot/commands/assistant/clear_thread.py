from bot.classes.command import command
from enums.bot_data import BotData
from modules.agent_runtime import AgentRuntime
from modules.memory import Memory


@command
async def clear_thread(update, context):
    """ Clears the thread """
    runtime: AgentRuntime = context.bot_data.get(BotData.AGENT_RUNTIME)
    if runtime:
        runtime.reset_history()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Thread cleared."
    )

    memory: Memory = context.bot_data.get(BotData.MEMORY, None)
    if memory:
        memory.clear_memory()

