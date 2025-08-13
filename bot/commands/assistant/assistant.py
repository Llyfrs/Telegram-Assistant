import datetime
import logging

import pytz


from pydantic_ai import Agent, capture_run_messages, ImageUrl, AudioUrl
from pydantic_ai.messages import ToolReturnPart, ToolCallPart
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, filters, MessageHandler

from bot.classes.command import Command
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.bot import Bot
from modules.database import ValkeyDB
from modules.memory import Memory
from modules.reminder import Reminders


costs = {
    "gpt-4o": 0.00500 / 1000,
    "gpt-4o-mini": 0.000150 / 1000,
    "o3-mini": 1.10 / 1000000
}

## TODO: Move this to a separate file at some point, it's here to just clean up the main file
def get_current_time():

    cet = pytz.timezone('CET')
    current_time_and_date = datetime.datetime.now(cet)
    current_time_and_date = current_time_and_date.strftime("%H:%M:%S %d/%m/%Y")

    print("Returning time: " + str(current_time_and_date))
    return {"current_time": current_time_and_date}


def split_text(text, max_length=2500):
    """
    Splits the input text into chunks not exceeding max_length characters.
    Splitting is done at the nearest newline or space to avoid breaking words.
    """
    chunks = []
    while len(text) > max_length:
        # Try to split at the last newline within the limit
        split_index = text.rfind('\n', 0, max_length)
        if split_index == -1:
            # If no newline, try to split at the last space
            split_index = text.rfind(' ', 0, max_length)
            if split_index == -1:
                # If no space, split at max_length
                split_index = max_length
        chunk = text[:split_index].rstrip()
        chunks.append(chunk)
        text = text[split_index:].lstrip()
    if text:
        chunks.append(text)
    return chunks

class Assistant(Command):
    register = False
    priority = -1
    messages = []

    @classmethod
    def handler(cls, app):
        app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND, Assistant.handle), group=0)

    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):

        print("Handling message in Assistant command")

        main_agent : Agent = context.bot_data[BotData.MAIN_AGENT]
        reminder : Reminders = context.bot_data[BotData.REMINDER]

        memory : Memory = context.bot_data.get(BotData.MEMORY, None)

        reminder.chat_id = update.effective_chat.id
        bot = Bot(context.bot, update.effective_chat.id)

        ## Change status to typing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        print(update)

        ## This whole think is broken as if you send more that one image they all get registered as a separate message
        photos = []
        if len(update.message.photo):
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)  # Renamed to clarify
            photos.append(file.file_path)

        audio_url = None
        if update.message.voice:
            audio = update.message.voice
            file = await context.bot.get_file(audio.file_id)
            audio_url = file.file_path
            print(audio_url)

        # HH:MM format
        time_text = update.message.date.strftime("%H:%M")

        message = [f"Send at {time_text}: " + (update.message.text or " ")]


        if len(photos) != 0:
            logging.info(f"User sent {len(photos)} photos")
            message = [ update.message.caption, ImageUrl(url=photos[0])]

        elif audio_url is not None:
            logging.info("User sent a voice message")
            message = [ "Listen to the audio", AudioUrl(url=audio_url) ]

        ## Has to be before we call agent as that will make sure at least one message is added to the memory
        memory.add_message(role="User", content=update.message.text or "Text Not Found", role_type="user")

        messages = context.bot_data.get(BotData.MESSAGE_HISTORY, [])

        response = await main_agent.run(message, message_history=messages)

        chunks = split_text(response.output)
        for chunk in chunks:
            memory.add_message(role="Telegram Assistant", content=chunk, role_type="assistant")

        context.bot_data[BotData.MESSAGE_HISTORY] = response.all_messages()

        tool_calls = {}
        for msg in response.new_messages():
            parts = msg.parts
            for part in parts:
                if isinstance(part, ToolCallPart):
                    tool_calls[part.tool_call_id] = {
                        "name": part.tool_name,
                        "args": part.args,
                    }

                if isinstance(part, ToolReturnPart):
                    tool_calls[part.tool_call_id]["output"] = part.content


        for tool_call_id, tool_call in tool_calls.items():

            content = f"{tool_call['name']}({tool_call['args']}) => {tool_call.get('output', '')}"

            if len(content) > 2400:
                continue

            memory.add_message(
                role=tool_call["name"],
                content=f"{tool_call['name']}({tool_call['args']}) => {tool_call['output']}",
                role_type="tool"
            )

        db = ValkeyDB()
        if db.get_serialized(DatabaseConstants.DEBUG, False):
            for tool_call_id, tool_call in tool_calls.items():
                await bot.send(f"`{tool_call['name']}({tool_call['args']}) => {tool_call['output']}`")

        await bot.send(response.output)