from bot.classes.command import command
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.calendar import Calendar
from modules.database import ValkeyDB


@command
async def email_here(update, context):
    """ Sends the email address of the bot """
    ValkeyDB().set_serialized(DatabaseConstants.EMAIL_CHAT_ID, update.effective_chat.id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Email chat set. Emails will now be sent to this chat."
    )

