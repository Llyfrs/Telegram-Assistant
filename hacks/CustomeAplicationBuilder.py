import logging

from telegram.ext import Application, ApplicationBuilder

from commands.command import Command


## Imports all the commands, that makes them register themselves and available to the bot
## This is somewhat ugly but the beauty of it is that you can just now create new commands without having to import them anywhere
## It's obviously depended on specific folder name but this is sacrifice I'm willing to make
import importlib, glob, os; [importlib.import_module(f"commands.{os.path.basename(f)[:-3]}") for f in glob.glob("commands/*.py")]

class CustomApplicationBuilder(ApplicationBuilder):
    def build(self) -> Application:
        app = super().build()

        # Register commands
        command_list = []
        for name, cmd_cls in Command.commands.items():
            cmd_cls.handler(app)
            if issubclass(cmd_cls, Command):
                command_list.append((name, cmd_cls.get_description()))

        # Set bot commands in Telegram UI
        if command_list:
            logging.info(f"Setting commands: {command_list}")
            app.bot.set_my_commands(command_list)


        logging.info("CustomApplicationBuilder: Done")

        return app