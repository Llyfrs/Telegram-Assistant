"""Time Capsule watcher - delivers capsules when their time has come."""

import logging
from datetime import datetime

from telegram.ext import ContextTypes
from telegramify_markdown import markdownify

from bot.classes.watcher import run_repeated
from modules.time_capsule import get_pending_capsules, mark_as_sent

logger = logging.getLogger(__name__)


def format_capsule_message(message: str, created_at: datetime) -> str:
    """Format a time capsule with distinctive styling."""
    
    # Calculate how long ago it was created
    now = datetime.utcnow()
    delta = now - created_at
    days_ago = delta.days
    
    if days_ago < 7:
        time_ago = f"{days_ago} days ago"
    elif days_ago < 30:
        weeks = days_ago // 7
        time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
    elif days_ago < 365:
        months = days_ago // 30
        time_ago = f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = days_ago // 365
        time_ago = f"{years} year{'s' if years > 1 else ''} ago"
    
    created_str = created_at.strftime("%B %d, %Y")
    
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━
📜 *TIME CAPSULE OPENED* 📜
━━━━━━━━━━━━━━━━━━━━━━━━

*From:* You, {time_ago}
*Written on:* {created_str}

─────────────────────────

{message}

─────────────────────────"""


@run_repeated(interval=1800)  # Check every 30 minutes
async def time_capsule_delivery(context: ContextTypes.DEFAULT_TYPE):
    """Check for and deliver any pending time capsules."""
    
    pending = get_pending_capsules()
    
    if not pending:
        return
    
    logger.info(f"Delivering {len(pending)} time capsule(s)")
    
    for capsule in pending:
        try:
            formatted_message = format_capsule_message(
                message=capsule.message,
                created_at=capsule.created_at
            )
            
            await context.bot.send_message(
                chat_id=capsule.chat_id,
                text=markdownify(formatted_message),
                parse_mode="MarkdownV2"
            )
            
            mark_as_sent(capsule.capsule_id)
            logger.info(f"Delivered time capsule {capsule.capsule_id}")
            
        except Exception as exc:
            logger.error(f"Failed to deliver time capsule {capsule.capsule_id}: {exc}")

