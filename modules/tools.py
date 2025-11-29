""" Tools module
This file is containing tools that I use around the bot, it helps me keep the code clean and organized.
"""

import re

from modules.file_system import DiskFileSystem
from utils.logging import get_logger

logger = get_logger(__name__)


def escape_chars(match):
    char = match.group(0)
    return '\\' + char

def code_block(code: str):
    return "```py\n" + re.sub(r"`", r"\`", code) + "\n```"


def debug(steps):
    """ Debug
    This function generates debug messages from the steps object
    The idea it that function calls can be returned as a one message while tools like code interpreter get their own block.
    The string is return formatted for MarkdownV2
    """
    message_index = 0
    debug_messages = [""]

    if steps is None:
        return ["No steps found"]

    data = list(steps.data)
    data.reverse()

    for step in data:

        logger.debug("Processing step: %s", step)

        if step.type == "message_creation":
            continue

        if step.type == "tool_calls":

            for tool_call in step.step_details.tool_calls:
                logger.debug("Tool call: %s", tool_call)
                if tool_call.type == "function":
                    debug_messages[message_index] += re.sub(r"[_*()\[\]~`>#+\-=|{}.!\\]", escape_chars,
                                                            f"{tool_call.function.name}( {tool_call.function.arguments}) => {tool_call.function.output}) \n")

                if tool_call.type == "code_interpreter":
                    debug_messages.append(f"Code Interpeter {code_block(tool_call.code_interpreter.input)}")
                    debug_messages[message_index + 1] += re.sub(r"[_*()\[\]~`>#+\-=|{}.!\\]", escape_chars,
                                                                f" \n Output: {tool_call.code_interpreter.outputs}")
                    debug_messages.append("")
                    message_index += 2

    if debug_messages[message_index] == "":
        debug_messages.pop(message_index)

    """Looks like it shouldn't be reversed. Even thous it acted like it should be."""
    return debug_messages


def init_file_manager():
    """Initialize file manager"""
    file_manager = DiskFileSystem()
    file_manager.mkdir("memory")
    file_manager.mkdir("logs")
    file_manager.create_file("logs/logs.txt", "Log file created")
    file_manager.mkdir("daily")

    return file_manager
