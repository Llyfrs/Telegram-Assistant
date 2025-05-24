import logging

import telegram
import telegramify_markdown


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
                    logging.error(f"Failed to clean last message: {e} in message: {text}")

                self.last_messages[caller_id] = message

            return message

        except Exception as exc:
            logging.error(f"Error sending message: {exc}")

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
            logging.error(f"Error editing message: {exc}")
