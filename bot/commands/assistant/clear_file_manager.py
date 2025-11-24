from bot.classes.command import command
from enums.bot_data import BotData
from modules.tools import init_file_manager
import shutil
from pathlib import Path

@command
async def clear_files(update, context):
    """ Clears the file manager """
    # Re-initialize to ensure structure (this creates 'storage' if missing, etc)
    # To "clear", we probably want to wipe the storage directory.
    
    # We need to be careful not to delete the class instance, but the files.
    # However, context.bot_data[BotData.FILE_MANAGER] holds the instance.
    
    # Let's just wipe the storage folder content and re-init.
    
    storage_path = Path("storage")
    if storage_path.exists():
        for item in storage_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
                
    # Re-init to recreate default structure (Logs, Memory, Daily)
    context.bot_data[BotData.FILE_MANAGER] = init_file_manager()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="File manager cleared."
    )
