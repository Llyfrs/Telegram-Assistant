import asyncio
import logging
from time import sleep
from typing import Optional

import telegram
from imap_tools import MailBox, AND
import os

from typing import Union
from pydantic.json_schema import GenerateJsonSchema
from telegramify_markdown import markdownify

import openai_api
from pydantic import BaseModel, Field


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
                                "If the email seems suspicious or it's advertisement mark it as spam and don't provide a summary. "
                                "You are free to use markdown to format the response.",
                    message=f'{e.subject} {e.text}',
                    schema=EmailResponse
                ).parsed
                self.reported.append(e.uid)

                if response.spam:
                    self.move_email(e, self.spam_folder)

                summary.append((e, response))

        return summary


# Custom schema generator
## This is interesting, so two things here.
## The openAI doesn't accept schema that has anyOf values in it, and that is what get's generated when you use Optional or | in pydantic.
## So to make it work you have to add your own extra json_schema_extra to the field.
## Second thing I noticed is that the order matters, it is safe to assume the AI generates the json in order, so if like in this case the summary is optional
## and depended on the spam value, it has to be later in the schema.
## Having the summary be none fro spam will hopefully save few cents on the API calls.
class EmailResponse(BaseModel):
    spam: bool
    summary: Optional[str] = Field(default=None, json_schema_extra={'type': ['string', 'null']})
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

    errors = 0

    while True:
        try:
            summary = email.summarize_new()

            if len(summary) > 0:
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
            logging.error(f"Email Error: {e}")
            errors += 1

            if errors > 3:
                logging.error("Too many errors pausing email bot")
                await asyncio.sleep(60 * 10)


        await asyncio.sleep(100)


if __name__ == "__main__":


    print(EmailResponse.model_json_schema())

    email = Email(
        os.getenv("EMAIL_ADDRESS"),
        os.getenv("EMAIL_PASSWORD"),
        os.getenv("IMAP_SERVER"),
        os.getenv("IMAP_PORT")
    )

    email.set_spam_folder("AI Spam")
    email.add_excluded_folder("AI Spam")
    email.add_excluded_folder("spam")
    email.add_excluded_folder("trash")
    email.add_excluded_folder("Administrativa")



    for e, response in email.summarize_new():
        print(f"Subject: {e.subject}")
        print(f"Summary: {response.summary}")
        print(f"Spam: {response.spam}")
        print(f"Important: {response.important}")
        print("")