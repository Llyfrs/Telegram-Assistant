import asyncio
import logging

from telegram.ext import Application, ApplicationBuilder

from bot.classes.command import Command
from bot.classes.watcher import Watcher


class CustomApplicationBuilder(ApplicationBuilder):
    def build(self) -> Application:
        app = super().build()

        # Register commands
        command_list = []

        commands = sorted(Command.commands.items(), key=lambda x: x[1].priority, reverse=True)

        for name, cmd_cls in commands:

            logging.info(f"Registering command: {name}")

            cmd_cls.handler(app)
            if issubclass(cmd_cls, Command) and cmd_cls.register:
                command_list.append((name, cmd_cls.get_description()))

        # Set bot commands in Telegram UI
        if command_list:
            logging.info(f"Setting commands: {command_list}")
            loop = asyncio.get_event_loop()
            loop.run_until_complete(app.bot.set_my_commands(command_list))


        for name in Watcher.watchers:
            Watcher.watchers[name].setup(app)



        logging.info("CustomApplicationBuilder: Done")

        return app