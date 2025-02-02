import logging
from http.client import responses
from pyexpat.errors import messages
from time import sleep

import telegram
from imap_tools import MailBox, AND
import os

from telegramify_markdown import markdownify

import openai_api

from pydantic import BaseModel

from modules.database import ValkeyDB


class Email:

    def __init__(self, address, password, imap_server, port):
        self.address = address
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.excluded_folders = []
        self.spam_folder = "spam"
        self.reported = []

        self.client = openai_api.OpenAI_API(os.getenv("OPENAI_KEY"))


    def add_excluded_folder(self, folder):
        self.excluded_folders.append(folder)

    def set_spam_folder(self, folder):
        self.spam_folder = folder


    def get_mailboxes(self):
        with MailBox(self.imap_server).login(self.address, self.password) as mailbox:
            return [box.name for box in mailbox.folder.list()]


    def get_unread_emails(self):
        with MailBox(self.imap_server).login(self.address, self.password) as mailbox:

            folders = self.get_mailboxes()
            folders = [folder for folder in folders if folder not in self.excluded_folders]

            result = []

            for folder in folders:
                mailbox.folder.set(folder)
                for e in mailbox.fetch(AND(seen=False), mark_seen=False):
                    result.append(e)
            return result

    def move_email(self, email, folder):
        with MailBox(self.imap_server).login(self.address, self.password) as mailbox:
            mailbox.move(email.uid, folder)

    def summarize_new(self):
        summary = []
        unread = self.get_unread_emails()

        for e in unread:
            if e.uid not in self.reported:
                response : EmailResponse = self.client.simple_completion(
                    instruction="Summarize the email (in it's original language) as much as possible the summary just needs to give overview not pass over all information. "
                                "If the email seems suspicious or it's advertisement mark it as spam."
                                "You are free to use markdown to format the response.",
                    message=f'{e.subject} {e.text}',
                    schema=EmailResponse
                ).parsed
                self.reported.append(e.uid)

                if response.spam:
                    self.move_email(e, self.spam_folder)

                summary.append((e, response))

        return summary





class EmailResponse(BaseModel):
    summary: str
    spam: bool
    important: bool


async def email_updates(bot: telegram.Bot, chat_id: str):
    email = Email(
        os.getenv("EMAIL"),
        os.getenv("EMAIL_PASSWORD"),
        os.getenv("IMAP_SERVER"),
        os.getenv("IMAP_PORT")
    )


    ## Definitely very individual to the user, should probably be latter moved to settings
    email.set_spam_folder("AI Spam")
    email.add_excluded_folder("AI Spam")
    email.add_excluded_folder("spam")
    email.add_excluded_folder("trash")
    email.add_excluded_folder("Administrativa")

    logging.info("Email bot started")

    while True:
        try:
            summary = email.summarize_new()

            logging.info(f"Processing {len(summary)} new emails")

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

                await bot.send_message(
                    chat_id=chat_id,
                    text=markdownify(message),
                    parse_mode="MarkdownV2"
                )

        except Exception as e:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Error: {e}"
            )

        sleep(60)
