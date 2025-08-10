from bot.classes.command import command
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import ValkeyDB
from modules.tools import init_file_manager


@command
async def clear_files(update, context):
    """ Clears the file manager """
    context.bot_data[BotData.FILE_MANAGER] = init_file_manager()
    ValkeyDB().set_serialized(DatabaseConstants.FILE_MANAGER,context.bot_data[BotData.FILE_MANAGER])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="File manager cleared."
    )

