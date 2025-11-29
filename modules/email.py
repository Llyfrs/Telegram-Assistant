from imap_tools import MailBox, AND
import os

from agents.email_summary_agent import get_email_summary_agent, EmailResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class Email:

    def __init__(self, address, password, imap_server, port):
        self.address = address
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.excluded_folders = []
        self.spam_folder = "spam"
        self.reported = []

        self.client = get_email_summary_agent()


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

    async def summarize_new(self):
        summary = []
        unread = self.get_unread_emails()

        for e in unread:
            if e.uid not in self.reported:
                response : EmailResponse = (await self.client.run(f"{e.subject} {e.text} \n timestamp: {e.date.isoformat()}")).output
                self.reported.append(e.uid)

                if response.spam:
                    self.move_email(e, self.spam_folder)

                summary.append((e, response))

        return summary



if __name__ == "__main__":
    from utils.logging import setup_logging
    setup_logging()

    logger.info("Schema: %s", EmailResponse.model_json_schema())

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
        logger.info("Subject: %s", e.subject)
        logger.info("Summary: %s", response.summary)
        logger.info("Spam: %s", response.spam)
        logger.info("Important: %s", response.important)