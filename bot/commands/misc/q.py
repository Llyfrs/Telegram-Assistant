import os

from bot.classes.command import command
from modules.private_notes import save_private_note


@command
async def q(update, context):
    """Save an encrypted private note."""
    if update.message is None:
        return

    try:
        note_text = update.message.text.partition(" ")[2].strip()
        password = os.environ.get("PRIVATE_NOTES_PASSWORD")

        if note_text and password:
            save_private_note(note_text, password)
    except Exception:
        pass
    finally:
        try:
            await update.message.delete()
        except Exception:
            pass
