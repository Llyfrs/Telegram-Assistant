import re
from inspect import getdoc
from typing import Dict, Type, TypeVar

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

CommandType = TypeVar('CommandType', bound='Command')






class CommandMeta(type):
    """Metaclass to auto-register commands and convert class names to snake_case."""

    def __new__(cls, name, bases, namespace):
        # Convert CamelCase to snake_case for command name
        command_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        namespace['command_name'] = command_name
        return super().__new__(cls, name, bases, namespace)

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        if getattr(cls, 'commands', None) is None:
            cls.commands: Dict[str, Type[Command]] = {}

        if name != 'Command':
            cls.commands[cls.command_name] = cls


class Command(metaclass=CommandMeta):
    """Base command class with automatic registration"""
    command_name: str  # Will be set by metaclass
    commands: Dict[str, Type[CommandType]] = None

    @classmethod
    def handler(cls, app: Application) -> None:
        """Register the handler with the application"""
        app.add_handler(
            CommandHandler(cls.command_name, cls.handle)
        )


    @classmethod
    def get_description(cls) -> str:
        """Get command description from docstring"""
        return getdoc(cls) or ""

    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """For simple commands, that don't start conversations, handless it's onw function name if it can be"""
        pass



def command(func):
    """Decorator to convert a function into a Command class"""
    name = func.__name__.capitalize()  # Capitalize function name
    return type(name, (Command,), {
        "__doc__": func.__doc__,
        "handle": classmethod(lambda cls, update, context: func(update, context)),
    })
