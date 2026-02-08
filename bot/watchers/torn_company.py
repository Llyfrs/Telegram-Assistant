from datetime import datetime, time, timedelta
from typing import Optional

import pytz
from telegram.ext import ContextTypes

from bot.classes.watcher import Watcher
from enums.bot_data import BotData
from modules.database import MongoDB
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
        if not MongoDB().get("notify_company_update", False):
            return

        torn = cls._get_torn(context)
        if torn is None:
            return

        await torn.update_company()
        logger.info("Company data updated by watcher")


class TornStockWatcher(_DailyTornWatcher):
    target_time = time(7, 0)

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not MongoDB().get("notify_stock_report", False):
            return

        torn = cls._get_torn(context)
        if torn is None:
            return

        await send_stock_report(torn)


class TornTrainWatcher(_DailyTornWatcher):
    target_time = time(7, 0)

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not MongoDB().get("notify_train_report", False):
            return

        torn = cls._get_torn(context)
        if torn is None:
            return

        await send_train_status(torn)


class TornStockClearWatcher(Watcher):
    interval = 60

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not MongoDB().get("notify_stock_clear", False):
            return

        torn = _DailyTornWatcher._get_torn(context)
        if torn is None:
            return

        await torn.update_company()

        if torn.company is None:
            return

        company_stock = torn.company.get("company_stock", {})
        try:
            total_in_stock = sum(float(v.get("in_stock", 0)) + float(v.get("on_order", 0)) for v in company_stock.values())
        except (TypeError, ValueError) as exc:
            logger.error("Failed to aggregate company stock data in clear watcher: %s", exc)
            return

        last_stock = MongoDB().get("company_stock_count", 0)

        if total_in_stock > last_stock:
            await torn.clear_by_name("send_stock_report")

        MongoDB().set("company_stock_count", total_in_stock)


class TornTrainClearWatcher(Watcher):
    interval = 60

    @classmethod
    async def job(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not MongoDB().get("notify_train_clear", False):
            return

        torn = _DailyTornWatcher._get_torn(context)
        if torn is None:
            return

        await torn.update_company()

        if torn.company is None:
            return

        detailed = torn.company.get("company_detailed", {})
        trains_available = detailed.get("trains_available", 0)

        last_trains = MongoDB().get("company_train_count", 0)

        if trains_available < last_trains:
            await torn.clear_by_name("send_train_status")

        MongoDB().set("company_train_count", trains_available)
