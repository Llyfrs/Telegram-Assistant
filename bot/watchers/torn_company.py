from datetime import datetime, time, timedelta
from typing import Optional

import pytz
from telegram.ext import ContextTypes

from bot.classes.watcher import Watcher
from enums.bot_data import BotData
from modules.torn import Torn
from modules.torn_tasks import send_stock_report, send_train_status
from utils.logging import get_logger

logger = get_logger(__name__)


def _seconds_until(target: time, tz) -> float:
    now = datetime.now(tz)
    target_datetime = now.replace(
        hour=target.hour,
        minute=target.minute,
        second=target.second,
        microsecond=0
    )
    if target_datetime <= now:
        target_datetime += timedelta(days=1)
    return (target_datetime - now).total_seconds()


class _DailyTornWatcher(Watcher):
    timezone = pytz.timezone("CET")
    interval = 24 * 60 * 60
    target_time = time(0, 0)

    @classmethod
    def setup(cls, app):
        if app.job_queue is None:
            raise ValueError("Application instance does not have a job queue.")

        first = _seconds_until(cls.target_time, cls.timezone)
        app.job_queue.run_repeating(cls.job, interval=cls.interval, first=first)

    @classmethod
    def _get_torn(cls, context: ContextTypes.DEFAULT_TYPE) -> Optional[Torn]:
        torn = context.application.bot_data.get(BotData.TORN)
        if torn is None:
            logger.warning("Torn instance not available for watcher %s", cls.__name__)
        return torn


class TornCompanyUpdateWatcher(_DailyTornWatcher):
    target_time = time(6, 50)

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        torn = cls._get_torn(context)
        if torn is None:
            return

        await torn.update_company()
        logger.info("Company data updated by watcher")


class TornStockWatcher(_DailyTornWatcher):
    target_time = time(7, 0)

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        torn = cls._get_torn(context)
        if torn is None:
            return

        await send_stock_report(torn)


class TornTrainWatcher(_DailyTornWatcher):
    target_time = time(7, 0)

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        torn = cls._get_torn(context)
        if torn is None:
            return

        await send_train_status(torn)
