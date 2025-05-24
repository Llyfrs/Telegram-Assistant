"""

Example file of two ways to implement simple ask / response commands. 
Creating class provides you with more flexibility and allows you to use class variables and methods.
Class definition is also the only way to right now implement conversation handler.

"""
from bot.classes.command import command, Command


@command
async def ping(update, context):
    """Ping the bot"""
    await update.message.reply_text("pong")
    pass


class Pong(Command):
    """Pong the bot"""
    @classmethod
    async def handle(cls, update, context):
        await update.message.reply_text("ping")
        pass