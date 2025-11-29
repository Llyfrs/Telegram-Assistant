"""
Centralized logging configuration for TelegramAssistant.

This module provides a unified logging setup using Rich for colored,
readable console output across the entire project.
"""

import logging
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


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure root logger with Rich colored output.
    
    Call this once at application startup (in main.py) to configure
    logging for the entire application.
    
    Args:
        level: The logging level (default: logging.INFO)
    """
    # Configure the root logger with custom Rich handler
    logging.basicConfig(
        level=level,
        format="[dim]%(name)-14s[/] │ %(message)s",
        datefmt="[%X]",
        handlers=[
            ColumnRichHandler(
                console=console,
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=True,
                highlighter=NullHighlighter(),
            )
        ],
        force=True,  # Override any existing configuration
    )
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

