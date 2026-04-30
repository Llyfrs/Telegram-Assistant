"""
Centralized logging configuration for TelegramAssistant.

This module provides a unified logging setup using Rich for colored,
readable console output across the entire project.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from rich.highlighter import NullHighlighter

# Custom theme for log styling
custom_theme = Theme({
    "logging.level.info": "green",
    "logging.level.warning": "yellow", 
    "logging.level.error": "bold red",
    "logging.level.debug": "dim blue",
    "repr.str": "dim cyan",
})

console = Console(theme=custom_theme)

_setup_done = False
_run_log_path: Optional[Path] = None


class ColumnRichHandler(RichHandler):
    """Custom RichHandler with module name in its own column."""
    
    def emit(self, record: logging.LogRecord) -> None:
        # Shorten the module name to just the last part
        if "." in record.name:
            record.name = record.name.rsplit(".", 1)[-1]
        
        # Truncate if too long, pad if too short (fixed 14 char width)
        if len(record.name) > 14:
            record.name = record.name[:13] + "…"
        
        super().emit(record)


def get_logger(name: str) -> logging.Logger:
    """
    Factory for consistent logger creation across the project.
    
    Args:
        name: The logger name, typically __name__ of the calling module.
        
    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO) -> Optional[Path]:
    """
    Configure root logger with Rich colored output and optional per-run file log.

    Call this once at application startup (in main.py) to configure
    logging for the entire application.

    Environment:
        TELEGRAM_ASSISTANT_LOG_FILE: set to 0/false/no to disable file logging.
        TELEGRAM_ASSISTANT_LOG_DIR: directory for run log files (default: run_logs/ under cwd).

    Run log filenames use UTC timestamps so names are stable across timezones.

    Args:
        level: The logging level (default: logging.INFO)

    Returns:
        Resolved path to this process's log file, or None if file logging is off or failed.
    """
    global _setup_done, _run_log_path

    if _setup_done:
        return _run_log_path

    handlers: list[logging.Handler] = [
        ColumnRichHandler(
            console=console,
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=True,
            highlighter=NullHighlighter(),
        )
    ]

    log_file_enabled = os.environ.get(
        "TELEGRAM_ASSISTANT_LOG_FILE", "1"
    ).strip().lower() not in ("0", "false", "no")

    file_error: Optional[OSError] = None
    if log_file_enabled:
        raw_dir = os.environ.get("TELEGRAM_ASSISTANT_LOG_DIR", "").strip()
        base = Path(raw_dir) if raw_dir else Path("run_logs")
        # UTC — filename is independent of server local timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = base / ("telegram-assistant_%s_%s.log" % (ts, os.getpid()))
        try:
            base.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            handlers.append(fh)
            _run_log_path = log_path.resolve()
        except OSError as e:
            file_error = e
            _run_log_path = None

    logging.basicConfig(
        level=level,
        format="[dim]%(name)-14s[/] │ %(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    setup_logger = logging.getLogger(__name__)
    if file_error is not None:
        setup_logger.warning("Could not write per-run log file: %s", file_error)
    if _run_log_path is not None:
        setup_logger.info("Writing application logs to %s", _run_log_path)

    _setup_done = True
    return _run_log_path
