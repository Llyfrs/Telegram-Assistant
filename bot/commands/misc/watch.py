"""
/watch — live-update a Telegram message with a sandboxed file under storage/.
"""

import asyncio
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from telegram import Message, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.classes.command import Command, command
from enums.bot_data import BotData
from modules.file_system import DiskFileSystem
from utils.logging import get_logger

logger = get_logger(__name__)

ASK_PATH = 0

TELEGRAM_MAX = 4096
THROTTLE_SEC = 1.0
MTIME_POLL_SEC = 1.0


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    footer = "\n\n... [truncated for Telegram %s char limit]" % max_len
    return s[: max(0, max_len - len(footer))] + footer


def _format_watch_message(relative_path: str, body: str) -> str:
    header = "Watch: %s\n\n" % relative_path
    room = TELEGRAM_MAX - len(header)
    if room < 80:
        room = 80
    body = _truncate(body, room)
    full = header + body
    if len(full) > TELEGRAM_MAX:
        full = _truncate(full, TELEGRAM_MAX)
    return full


def _read_file_sync(fs: DiskFileSystem, relative_path: str) -> str:
    try:
        target = fs._resolve_path(relative_path)
        if not target.exists():
            return "[file not found]"
        if target.is_dir():
            return "[path is a directory]"
        return target.read_text(encoding="utf-8")
    except ValueError as e:
        return "[Error: %s]" % e
    except Exception as e:
        return "[Error: %s]" % e


async def _read_body_async(fs: DiskFileSystem, relative_path: str) -> str:
    return await asyncio.to_thread(_read_file_sync, fs, relative_path)


async def cancel_watch_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    tasks = context.bot_data.get(BotData.FILE_WATCH_TASKS)
    if not tasks:
        return
    task: Optional[asyncio.Task] = tasks.pop(chat_id, None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _watch_loop(
    application: Application,
    chat_id: int,
    message: Message,
    relative_path: str,
    resolved_path: Path,
) -> None:
    fs: DiskFileSystem = application.bot_data[BotData.FILE_MANAGER]
    last_edit = 0.0

    async def maybe_refresh() -> None:
        nonlocal last_edit
        now = time.monotonic()
        if now - last_edit < THROTTLE_SEC:
            await asyncio.sleep(THROTTLE_SEC - (now - last_edit))
        last_edit = time.monotonic()
        body = await _read_body_async(fs, relative_path)
        text = _format_watch_message(relative_path, body)
        try:
            await message.edit_text(text)
        except Exception as e:
            logger.warning("watch edit_text failed: %s", e)

    try:
        use_awatch = True
        try:
            from watchfiles import awatch
        except ImportError:
            use_awatch = False
            logger.info("watchfiles not installed; using mtime polling for /watch")

        if use_awatch:
            try:
                async for _ in awatch(str(resolved_path)):
                    await maybe_refresh()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("awatch failed (%s), falling back to mtime polling", e)
                await _mtime_poll_loop(resolved_path, maybe_refresh)
        else:
            await _mtime_poll_loop(resolved_path, maybe_refresh)
    except asyncio.CancelledError:
        raise
    finally:
        tasks = application.bot_data.get(BotData.FILE_WATCH_TASKS)
        if tasks and tasks.get(chat_id) is asyncio.current_task():
            tasks.pop(chat_id, None)


async def _mtime_poll_loop(
    resolved_path: Path,
    refresh: Callable[[], Awaitable[None]],
) -> None:
    last_mtime: Optional[float] = None
    try:
        last_mtime = resolved_path.stat().st_mtime
    except FileNotFoundError:
        last_mtime = None

    while True:
        await asyncio.sleep(MTIME_POLL_SEC)
        try:
            m = resolved_path.stat().st_mtime
        except FileNotFoundError:
            if last_mtime is not None:
                last_mtime = None
                await refresh()
            continue
        if last_mtime is None or m != last_mtime:
            last_mtime = m
            await refresh()


async def _begin_watch(update: Update, context: ContextTypes.DEFAULT_TYPE, relative_path: str) -> None:
    fs: DiskFileSystem = context.bot_data[BotData.FILE_MANAGER]
    relative_path = relative_path.strip().strip("/")
    try:
        target = fs._resolve_path(relative_path)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    if not target.exists():
        await update.message.reply_text("Error: file not found for path `%s`" % relative_path)
        return
    if target.is_dir():
        await update.message.reply_text("Error: `%s` is a directory; choose a file." % relative_path)
        return

    await cancel_watch_for_chat(context, update.effective_chat.id)

    body = await _read_body_async(fs, relative_path)
    text = _format_watch_message(relative_path, body)
    msg = await update.message.reply_text(text)

    task = context.application.create_task(
        _watch_loop(
            context.application,
            update.effective_chat.id,
            msg,
            relative_path,
            target,
        )
    )
    tasks = context.bot_data.setdefault(BotData.FILE_WATCH_TASKS, {})
    tasks[update.effective_chat.id] = task


async def watch_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        rel = " ".join(context.args).strip()
        if rel:
            await _begin_watch(update, context, rel)
            return ConversationHandler.END

    await update.message.reply_text(
        "Send a path relative to `storage/` (e.g. `logs/logs.txt`).\n"
        "Use /cancel to abort."
    )
    return ASK_PATH


async def watch_receive_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip()
    if not raw:
        await update.message.reply_text("Send a non-empty path, or /cancel.")
        return ASK_PATH
    await _begin_watch(update, context, raw)
    return ConversationHandler.END


async def watch_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


class WatchHandler:
    @staticmethod
    def get_conversation_handler() -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler("watch", watch_start)],
            states={
                ASK_PATH: [MessageHandler(filters.TEXT & ~filters.COMMAND, watch_receive_path)],
            },
            fallbacks=[CommandHandler("cancel", watch_cancel)],
            map_to_parent={ConversationHandler.END: -1},
        )


class Watch(Command):
    """Watch a file under storage/; message updates when the file changes."""

    @classmethod
    def handler(cls, app: Application) -> None:
        app.add_handler(WatchHandler.get_conversation_handler())


@command
async def unwatch(update, context):
    """Stop the active file watch in this chat."""
    await cancel_watch_for_chat(context, update.effective_chat.id)
    await update.message.reply_text("File watch stopped.")
