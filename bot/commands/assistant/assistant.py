import datetime
import logging

import pytz


from pydantic_ai import ImageUrl, AudioUrl
from pydantic_ai.messages import ToolReturnPart, ToolCallPart
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, filters, MessageHandler

from bot.classes.command import Command
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.agent_runtime import AgentRuntime, QueuedMessage
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

        reminder: Reminders = context.bot_data[BotData.REMINDER]
        runtime: AgentRuntime = context.bot_data[BotData.AGENT_RUNTIME]

        memory: Memory = context.bot_data.get(BotData.MEMORY, None)

        reminder.chat_id = update.effective_chat.id
        bot = Bot(context.bot, update.effective_chat.id)

        runtime.set_default_chat(update.effective_chat.id)

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

        direct_message_note = (
            "This is direct request on telegram and your response is expected "
            "with at least one send message."
        )

        base_text = update.message.text or update.message.caption or ""
        base_text = base_text.strip()

        agent_message = []
        header_text = f"Sent at {time_text}"

        if len(photos) != 0:
            logging.info(f"User sent {len(photos)} photos")
            description = base_text if base_text else "User sent a photo."
            agent_message.append(f"{header_text}: {description}")
            agent_message.append(ImageUrl(url=photos[0]))

        elif audio_url is not None:
            logging.info("User sent a voice message")
            description = base_text if base_text else "User sent a voice message."
            agent_message.append(f"{header_text}: {description}")
            agent_message.append(AudioUrl(url=audio_url))

        else:
            description = base_text if base_text else "(no text provided)"
            agent_message.append(f"{header_text}: {description}")

        agent_message.append(direct_message_note)

        if memory:
            memory.add_message(
                role="User",
                content=base_text or "[no textual content provided]",
                role_type="user",
            )

        response = await runtime.run(agent_message)

        if memory and response.output:
            chunks = split_text(response.output)
            for chunk in chunks:
                memory.add_message(role="Telegram Assistant", content=chunk, role_type="assistant")

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

        queued_messages: list[QueuedMessage] = runtime.drain_outgoing()

        for queued in queued_messages:
            target_bot = bot if queued.chat_id == update.effective_chat.id else Bot(context.bot, queued.chat_id)
            await target_bot.send(
                queued.text,
                clean=queued.clean,
                markdown=queued.markdown,
            )
            if memory:
                memory.add_message(role="Telegram Assistant", content=queued.text, role_type="assistant")

