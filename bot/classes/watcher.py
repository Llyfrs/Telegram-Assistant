import re
from datetime import time, datetime
from typing import Dict, Type, Optional, Callable, Tuple, Union, TypeVar
from telegram.ext import Application, ContextTypes

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

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Periodic task to execute. Override this in subclasses."""
        pass


def run_repeated(interval=60, first=None, last=None, **kwargs):
    """Decorator to schedule a repeating job."""
    return _create_watcher_decorator('run_repeating', interval=interval, first=first, last=last, **kwargs)


def run_daily(time: Union[time, Tuple[int, int, int]], days=(0, 1, 2, 3, 4, 5, 6), **kwargs):
    """Decorator to schedule a daily job."""
    return _create_watcher_decorator('run_daily', time=time, days=days, **kwargs)


def run_monthly(when: Union[time, Tuple[int, int, int]], day: int, **kwargs):
    """Decorator to schedule a monthly job."""
    return _create_watcher_decorator('run_monthly', when=when, day=day, **kwargs)


def run_once(when: datetime, **kwargs):
    """Decorator to schedule a one-time job."""
    return _create_watcher_decorator('run_once', when=when, **kwargs)


def _create_watcher_decorator(schedule_method: str, **schedule_kwargs):
    """Helper function to create watcher decorators."""
    def decorator(func: Callable[ [ContextTypes.DEFAULT_TYPE, ...] , None] ) -> Type:
        class_name = func.__name__.capitalize()
        watcher_cls = type(class_name, (Watcher,), {'job': staticmethod(func)})
        watcher_cls.setup = classmethod(lambda cls, app: getattr(app.job_queue, schedule_method)(cls.job, **schedule_kwargs))
        return watcher_cls

    return decorator