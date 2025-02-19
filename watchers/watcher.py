import re
from typing import Dict, Type, TypeVar
from abc import ABCMeta
from telegram.ext import Application, ContextTypes
from inspect import getdoc

WatcherType = TypeVar('WatcherType', bound='Watcher')


class WatcherMeta(type):
    """Metaclass to auto-register watchers and convert class names to snake_case."""

    def __new__(cls, name, bases, namespace):
        if name != 'Watcher':
            watcher_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
            namespace['watcher_name'] = watcher_name
        return super().__new__(cls, name, bases, namespace)

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        if getattr(cls, 'watchers', None) is None:
            cls.watchers: Dict[str, Type[Watcher]] = {}
        if name != 'Watcher':
            cls.watchers[cls.watcher_name] = cls


class Watcher(metaclass=WatcherMeta):
    """Base watcher class with automatic registration and scheduling."""
    watcher_name: str
    watchers: Dict[str, Type[WatcherType]] = None
    interval: int = 60  # Default interval in seconds

    @classmethod
    def setup(cls, app: Application) -> None:
        """Schedule the watcher's job with the application's job queue."""
        if app.job_queue is None:
            raise ValueError("Application instance does not have a job queue.")
        app.job_queue.run_repeating(cls.job, interval=cls.interval, first=0)

    @staticmethod
    async def job(context: ContextTypes.DEFAULT_TYPE) -> None:
        """Periodic task to execute. Override this in subclasses."""
        pass


def watcher(_func=None, *, interval=60):
    """Decorator to create Watcher subclasses from async functions."""

    def decorator(func):
        class_name = func.__name__.capitalize()
        watcher_cls = type(
            class_name,
            (Watcher,),
            {
                'interval': interval,
                'job': staticmethod(func),
                '__doc__': func.__doc__,
            }
        )
        return watcher_cls

    return decorator(_func) if _func else decorator