import io

from telegram import Update, Document
from telegram.ext import MessageHandler, filters, ContextTypes

from bot.classes.command import Command
from enums.bot_data import BotData
from modules.memory import Memory
from utils.logging import get_logger

logger = get_logger(__name__)

TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-yaml",
}

class FileUploader(Command):
    register = False
    priority = -1
    messages = []

    @classmethod
    def handler(cls, app):
        app.add_handler(MessageHandler((filters.ATTACHMENT) & ~filters.COMMAND, cls.handle), group=0)

    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):

        memory : Memory = context.bot_data.get(BotData.MEMORY, None)

        if not update.message or not update.message.document:
            logger.debug("No document in message")
            return

        doc: Document = update.message.document
        mime = doc.mime_type
        file_id = doc.file_id
        logger.info("Received document: %s (%s)", doc.file_name, mime)

        if mime not in TEXT_MIME_TYPES:
            await update.message.reply_text(
                "Unsupported file type. Please upload a text-based file (e.g., .txt, .json, .md)."
            )
            return

        # Get the file object
        telegram_file = await context.bot.get_file(file_id)

        # Create an in-memory bytes buffer
        buffer = io.BytesIO()

        # Download the file into the buffer
        await telegram_file.download_to_memory(out=buffer)

        # Reset the buffer's position to the beginning
        buffer.seek(0)

        # Try to decode as UTF-8
        try:
            content = buffer.read().decode('utf-8')
            ## Chunks by 10k characters
            chunk_size = 10000
            chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            for chunk in chunks:
                memory.add_text_to_graph(
                    text=chunk,
                )

            await update.message.reply_text("File content added to memory. Might take a while to process.")

        except UnicodeDecodeError:
            logger.warning("Could not decode file as UTF-8")
