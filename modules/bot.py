import telegram
import telegramify_markdown

from io import BytesIO
from typing import Optional

from telegram import InputFile

from utils.logging import get_logger

logger = get_logger(__name__)


class Bot:
    """
    Wrapper around telegram.Bot to make sending messages consistent across the bot
    """

    def __init__(self, bot: telegram.Bot, chat_id):
        self.bot: telegram.Bot = bot
        self.chat_id = chat_id
        self.last_messages = {}  # Tracks last message sent by caller_id

    async def send(self, text, clean=True, markdown=True, caller_id=None):
        try:

            if len(text) > 4096:
                for i in range(0, len(text), 4000):
                    part = text[i:i + 4000]
                    await self.send(part, clean=clean, markdown=markdown, caller_id=caller_id)


            if markdown:
                text = telegramify_markdown.markdownify(text)

            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="MarkdownV2" if markdown else None,
            )

            if caller_id and clean:
                try:
                    previous_message = self.last_messages.get(caller_id)
                    if previous_message:
                        await self.bot.delete_message(
                            chat_id=self.chat_id,
                            message_id=previous_message.message_id,
                        )
                except Exception as e:
                    logger.error("Failed to clean last message: %s", e)

                self.last_messages[caller_id] = message

            return message

        except Exception as exc:
            logger.error("Error sending message: %s", exc)


    async def edit(self, message, text, markdown=True):
        try:
            if markdown:
                text = telegramify_markdown.markdownify(text)

            message = await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message.message_id,
                text=text,
                parse_mode="MarkdownV2" if markdown else None,
            )

            return message

        except Exception as exc:
            logger.error("Error editing message: %s", exc)

    async def send_photo(
        self,
        photo: BytesIO,
        caption: Optional[str] = None,
        markdown: bool = True,
        filename: str = "image.png",
    ):
        """
        Send an in-memory image to the configured chat.

        Args:
            photo: BytesIO containing the image data (e.g. PNG). Will be read from its current position.
            caption: Optional caption text.
            markdown: If True, caption is markdownified and sent as MarkdownV2.
            filename: Filename used for Telegram's upload metadata.
        """
        try:
            if caption and markdown:
                caption = telegramify_markdown.markdownify(caption)

            input_file = InputFile(photo, filename=filename)

            return await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=input_file,
                caption=caption,
                parse_mode="MarkdownV2" if (caption and markdown) else None,
            )
        except Exception as exc:
            logger.error("Error sending photo: %s", exc)
