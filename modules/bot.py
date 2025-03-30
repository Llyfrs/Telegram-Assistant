import inspect
import logging

import telegram
import telegramify_markdown


class Bot:
    """
    Warmer around telegram.Bot to make sending messages consistent across the bot

    it's TODO
    """

    def __int__(self, bot : telegram.Bot, chat_id):
        self.bot : telegram.Bot = bot
        self.chat_id = chat_id
        self.last_messages = {} ## Keeps track of last message send by specific function to clean it up later


    async def send(self, text, clean = True, markdown = True):
        try:

            text = telegramify_markdown.markdownify(text) if markdown else text
            message = await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="MarkdownV2" if markdown else None)

            ## Wild stuff this is, but it makes sure the bot cleans up after itself, at the same time it sends new message
            try:
                if inspect.stack()[1].function in self.last_messages and clean:
                    await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_messages[inspect.stack()[1].function].message_id)
            except Exception as e:
                logging.error(f"Failed to clean last message: {e} in message: {text}")

            self.last_messages[inspect.stack()[1].function] = message

            return message ## Return the message object

        except Exception as exc:
            logging.error(f"Error sending message: {exc}")


    async def edit(self, message, text, markdown = True):

        try:
            text = telegramify_markdown.markdownify(text) if markdown else text
            message = await self.bot.edit_message_text(chat_id=self.chat_id, message_id=message.message_id, text=text, parse_mode="MarkdownV2" if markdown else None)

            return message

        except Exception as exc:
            logging.error(f"Error editing message: {exc}")