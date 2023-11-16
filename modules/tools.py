""" Tools module
This file is containing tools that I use around the bot, it helps me keep the code clean and organized.
"""

import re


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
    for step in steps.data:
        print(f"Step: {step}")

        if step.type == "message_creation":
            continue

        if step.type == "tool_calls":

            for tool_call in step.step_details.tool_calls:
                print(tool_call)
                if tool_call.type == "function":
                    debug_messages[message_index] += re.sub(r"[_*()\[\]~`>#+\-=|{}.!]", escape_chars,
                                                            f"{tool_call.function.name}( {tool_call.function.arguments} ) => {tool_call.function.output}) \n")

                if tool_call.type == "code_interpreter":
                    debug_messages.append(f"Code Interpeter {code_block(tool_call.code_interpreter.input)}")
                    debug_messages[message_index + 1] += re.sub(r"[_*()\[\]~`>#+\-=|{}.!]", escape_chars,
                                                                f" \n Output: {tool_call.code_interpreter.outputs}")
                    debug_messages.append("")
                    message_index += 2

    if debug_messages[message_index] == "":
        debug_messages.pop(message_index)

    debug_messages.reverse()
    return debug_messages
