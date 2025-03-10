import datetime
import logging

import pytz
import telegramify_markdown
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, filters, MessageHandler


from commands.command import Command
from modules.database import ValkeyDB
from modules.tools import debug

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


class Assistant(Command):
    register = False

    priority = -1

    @classmethod
    def handler(cls, app):
        pass
        app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, Assistant.handle), group=0)

    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):

        client = context.bot_data["client"]
        reminder = context.bot_data["reminder"]

        reminder.chat_id = update.effective_chat.id

        ## Change status to typing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        print(update)

        photos = []
        if len(update.message.photo):
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)  # Renamed to clarify
            photos.append(file.file_path)

        message = update.message.text

        if len(photos) != 0:
            logging.info(f"User sent {len(photos)} photos")
            message = update.message.caption

        client.add_message(f"{get_current_time()['current_time']}: {message}", photos)

        steps = client.run_assistant()

        db = ValkeyDB()

        if db.get_serialized("debug", False):

            cost = client.last_run_cost
            dollar_cost = costs.get(client.model, 0) * cost.total_tokens

            long_time_cost = db.get_serialized("cost", 0)
            if long_time_cost is None:
                long_time_cost = 0

            db.set_serialized("cost", long_time_cost + dollar_cost)

            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"{cost.total_tokens} tokens used for price of ${round(dollar_cost, 5)}")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Total cost: ${round(long_time_cost + dollar_cost, 5)}")

            for dbg_msg in debug(steps):

                logging.info(dbg_msg)
                # TODO this need to be fixed ffs it's so ugly
                if dbg_msg == "":
                    continue

                await context.bot.send_message(chat_id=update.effective_chat.id, text=dbg_msg,
                                               parse_mode="MarkdownV2")

        # Sometimes the run is finished but the new message didn't arrive yet
        # so this will make sure we won't miss it
        messages = client.get_new_messages()
        while len(messages.data) == 0:
            messages = client.get_new_messages()
            return

        for message in messages:
            for content in message.content:
                if content.type == "text":
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=telegramify_markdown.markdownify(content.text.value),
                                                   parse_mode="MarkdownV2")

                if content.type == "image_file":
                    content = client.client.files.content(file_id=content.image_file.file_id)
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=content)