import logging

from telegram.ext import Application, CommandHandler
from commands.command import Command


class TestingTest(Command):

    @classmethod
    def handler(cls, app: Application) -> None:
        logging.info("TestingTest: handler")
        app.add_handler(
            CommandHandler("test", cls.handle)
        )

    @staticmethod
    async def handle( update, context ):
        await update.message.reply_text("Test")
        pass