from commands.command import command
from modules.database import ValkeyDB


@command
async def set_wolframalpha_app_id(update, context):
    """ Sets WolframAlpha app id """
    db = ValkeyDB()
    db.set_serialized("wolframalpha_app_id", update.message.text.split(" ")[1])
    await update.message.reply_text(f"WolframAlpha app id set")