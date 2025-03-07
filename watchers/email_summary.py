import datetime
import logging
import os
import asyncio

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, ContextTypes, CallbackQueryHandler
from telegramify_markdown import markdownify

from modules.database import ValkeyDB
from modules.email import Email, Event
from watchers.watcher import Watcher

from typing import Dict

logger = logging.getLogger(__name__)

class EmailSummary(Watcher):

    interval = 100
    email = Email(
        os.getenv("EMAIL"),
        os.getenv("EMAIL_PASSWORD"),
        os.getenv("IMAP_SERVER"),
        os.getenv("IMAP_PORT")
    )

    email.set_spam_folder("AI Spam")
    email.add_excluded_folder("AI Spam")
    email.add_excluded_folder("spam")
    email.add_excluded_folder("trash")
    email.add_excluded_folder("Administrativa")

    events : Dict[int, Event] = {}

    bot = None

    @classmethod
    def setup(cls, app: Application) -> None:
        """Schedule the watcher's job with the application's job queue."""

        logger.info("Setting up EmailSummary watcher")

        if app.job_queue is None:
            raise ValueError("Application instance does not have a job queue.")

        app.job_queue.run_repeating(cls.job, interval=cls.interval)

        app.add_handler(CallbackQueryHandler(cls.add_event, pattern="add_event"))
        app.add_handler(CallbackQueryHandler(cls.ignore_event, pattern="ignore_event"))

        cls.bot = app.bot

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:

        chat_id = ValkeyDB().get_serialized("chat_id")

        if chat_id is None:
            logger.error("chat_id is not set")
            return

        summary = cls.email.summarize_new()

        if len(summary) > 0:
            logger.info(f"Processing {len(summary)} new emails")

        for e, response in summary:

            if response.spam:
                continue

            message = "📨 *Email Received* \n\n"

            if response.important:
                message = "⚠️ *Important Email* \n\n"

            message += (
                f"📩 *From:* `{e.from_}`\n"
                f"📋 *Subject:* _{e.subject}_\n\n"
                f"📝 *Summary*\n"
                f"\n{response.summary}\n\n"
            )

            if len(e.attachments) > 0:
                message += "📎 *Attachments*\n"

            for attachment in e.attachments:
                message += f"• `{attachment.filename}`\n"

            await context.bot.send_message(
                chat_id=chat_id,
                text=markdownify(message),
                parse_mode="MarkdownV2"
            )

            if response.event:
               await cls.create_event(response.event)

        pass

    @classmethod
    async def create_event(cls, event: Event) -> bool:
        """Create an event from the callback query and add it to the calendar"""

        chat_id = ValkeyDB().get_serialized("chat_id")

        if chat_id is None:
            logger.error("chat_id is not set")
            return False

        start_string = "N/A" if event.start is None else datetime.datetime.fromisoformat(
            event.start).strftime("%Y-%m-%d %H:%M")

        end_string = "N/A" if event.end is None else datetime.datetime.fromisoformat(
            event.end).strftime("%Y-%m-%d %H:%M")

        message = await cls.bot.send_message(
            chat_id=chat_id,
            text=markdownify(
                f"📅 *Event - {event.title}*\n\n"
                f"📆 *Start:* {start_string}\n"
                f"📆 *End:* {end_string}\n"
                f"📝 *Description:* {event.description}\n"
            ),
            parse_mode="MarkdownV2",
            reply_markup=
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Add to Calendar", callback_data=f"add_event"),
                    InlineKeyboardButton("Ignore", callback_data=f"ignore_event")]
            ])

        )

        cls.events[message.id] = event

        return True

    @classmethod
    async def add_event(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from the watcher"""
        query = update.callback_query

        logger.info(f"Handling callback query: {query.data}")

        await query.answer()

        calendar = context.bot_data["calendar"]

        event = cls.events.pop(query.message.message_id)

        start = None if event.start is None else datetime.datetime.fromisoformat(event.start)
        end = None if event.end is None else datetime.datetime.fromisoformat(event.end)

        logger.info(f'Event is all day {event.all_day}')

        calendar.add_event(
            start=start,
            end=end,
            summary=event.title,
            description=event.description,
            all_day=event.all_day
        )

        await context.bot.edit_message_text(
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            text=markdownify(
                f"📅 *Event Added*\n\n"
                f"📆 *Start:* {event.start}\n"
                f"📆 *End:* {event.end}\n"
                f"📝 *Description:* {event.description}\n"
            ),
            parse_mode="MarkdownV2",
            reply_markup=None
        )

        pass


    @classmethod
    async def ignore_event(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from the watcher"""
        query = update.callback_query

        logger.info(f"Handling callback query: {query.data}")

        await query.answer()

        cls.events.pop(query.message.message_id)
        await context.bot.delete_message(
            chat_id=query.message.chat.id,
            message_id=query.message.message_id
        )

        pass



def blocking_add_event(event: Event) -> bool:

    logging.info(f"Blocking add event {event}")

    ## The delay hopefully makes the event confirmation message appear after the AI response, but it's not guaranteed.
    async def delayed_create_event():
        await asyncio.sleep(5)
        await EmailSummary.create_event(event)

    asyncio.create_task(delayed_create_event())
    return True


