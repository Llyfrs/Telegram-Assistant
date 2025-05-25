from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from bot.classes.command import Command

class LocationRecorder(Command):
    priority = -1
    register = False

    @classmethod
    def handler(cls, app):
        app.add_handler(MessageHandler(filters.LOCATION & ~filters.COMMAND, cls.handle), group=0)


    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle the location update

        if update.edited_message:
            print("Live Location Update received")
            pass

        if update.message and update.message.location.live_period is None:
            print("Manual location received")
