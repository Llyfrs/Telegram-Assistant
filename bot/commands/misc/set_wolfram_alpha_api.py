from bot.classes.command import command
from modules.database import MongoDB


@command
async def set_wolframalpha_app_id(update, context):
    """ Sets WolframAlpha app id """
    db = MongoDB()
    db.set("wolframalpha_app_id", update.message.text.split(" ")[1])
    await update.message.reply_text(f"WolframAlpha app id set")