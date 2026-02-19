from bot.classes.watcher import run_repeated
from enums.database import DatabaseConstants
from modules.database import MongoDB
from modules.private_notes import get_private_note_count

PRIVATE_NOTES_COUNT_KEY = "private_notes_last_count"


@run_repeated(interval=60)
async def private_notes_removed(context):
    db = MongoDB()
    current_count = get_private_note_count()
    previous_count = db.get(PRIVATE_NOTES_COUNT_KEY, current_count)

    if current_count < previous_count:
        chat_id = db.get(DatabaseConstants.MAIN_CHAT_ID)
        if chat_id is not None:
            if isinstance(chat_id, str):
                chat_id = int(chat_id)

            removed_count = previous_count - current_count
            if current_count == 0:
                text = "⚠️ Private notes database was emptied."
            else:
                text = f"⚠️ {removed_count} private note(s) were removed from private notes."

            await context.bot.send_message(chat_id=chat_id, text=text)

    db.set(PRIVATE_NOTES_COUNT_KEY, current_count)
