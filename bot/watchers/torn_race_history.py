from datetime import datetime

from telegram.ext import ContextTypes

from bot.classes.watcher import run_daily
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.database import MongoDB
from modules.torn import Torn
from structures.race_record import RaceResult
from utils.logging import get_logger

logger = get_logger(__name__)

BACKFILL_COMPLETE_KEY = "race_history_backfill_complete"


def _parse_races(races, torn, known_race_ids):
    """Parse race data from the API and return new RaceResult objects."""
    new_records = []

    for race in races:
        race_id = race.get("id")

        if race_id is None or race_id in known_race_ids:
            continue

        # Only save finished races
        if race.get("status") != "finished":
            continue

        schedule = race.get("schedule", {})
        participants = race.get("participants", {})
        requirements = race.get("requirements", {})
        results = race.get("results", [])

        # Find the user's own result
        user_result = None
        if torn.user and results:
            user_id = torn.user.get("player_id")
            for result in results:
                if result.get("driver_id") == user_id:
                    user_result = result
                    break

        # If we couldn't match by player_id, take the first result as a fallback
        # (the API returns user's races, so they should be in results)
        if user_result is None and results:
            logger.warning("Could not match user in race %d results, using first result as fallback", race_id)
            user_result = results[0]

        record = RaceResult(
            race_id=race_id,
            title=race.get("title", ""),
            track_id=race.get("track_id", 0),
            creator_id=race.get("creator_id", 0),
            status=race.get("status", ""),
            laps=race.get("laps", 0),
            is_official=race.get("is_official", False),
            schedule_join_from=schedule.get("join_from"),
            schedule_join_until=schedule.get("join_until"),
            schedule_start=schedule.get("start"),
            schedule_end=schedule.get("end"),
            participants_min=participants.get("minimum"),
            participants_max=participants.get("maximum"),
            participants_current=participants.get("current"),
            requirement_car_class=requirements.get("car_class"),
            requirement_driver_class=requirements.get("driver_class"),
            requirement_car_item_id=requirements.get("car_item_id"),
            requires_stock_car=requirements.get("requires_stock_car"),
            requires_password=requirements.get("requires_password"),
            join_fee=requirements.get("join_fee"),
            driver_id=user_result.get("driver_id") if user_result else None,
            position=user_result.get("position") if user_result else None,
            car_id=user_result.get("car_id") if user_result else None,
            car_item_id=user_result.get("car_item_id") if user_result else None,
            car_item_name=user_result.get("car_item_name") if user_result else None,
            car_class=user_result.get("car_class") if user_result else None,
            has_crashed=user_result.get("has_crashed") if user_result else None,
            best_lap_time=user_result.get("best_lap_time") if user_result else None,
            race_time=user_result.get("race_time") if user_result else None,
            time_ended=user_result.get("time_ended") if user_result else None,
            results=results,
            recorded_at=datetime.utcnow(),
        )

        record.save(key_field="race_id")
        known_race_ids.add(race_id)
        new_records.append(record)

    return new_records


async def _fetch_new_races(torn, known_race_ids, existing_records):
    """Fetch races newer than the latest stored race."""
    from_ts = None
    records_with_ts = [r for r in existing_records if r.schedule_start is not None]
    if records_with_ts:
        latest = max(records_with_ts, key=lambda r: r.schedule_start)
        from_ts = latest.schedule_start

    try:
        response = await torn.get_races(limit=100, sort="DESC", from_ts=from_ts)
    except Exception as e:
        logger.error("Failed to fetch new races: %s", e)
        return 0

    if response is None or response.get("error") is not None:
        logger.error("Torn API error fetching new races: %s", response)
        return 0

    races = response.get("races", [])
    if not races:
        return 0

    new_records = _parse_races(races, torn, known_race_ids)
    return len(new_records)


async def _fetch_past_races(torn, known_race_ids, existing_records, db):
    """Fetch one batch of races older than the oldest stored race (backfill)."""
    if db.get(BACKFILL_COMPLETE_KEY, False):
        return 0

    to_ts = None
    records_with_ts = [r for r in existing_records if r.schedule_start is not None]
    if records_with_ts:
        oldest = min(records_with_ts, key=lambda r: r.schedule_start)
        to_ts = oldest.schedule_start

    try:
        response = await torn.get_races(limit=100, sort="DESC", to_ts=to_ts)
    except Exception as e:
        logger.error("Failed to fetch past races: %s", e)
        return 0

    if response is None or response.get("error") is not None:
        logger.error("Torn API error fetching past races: %s", response)
        return 0

    races = response.get("races", [])
    if not races:
        # No more historical data available — backfill is done
        db.set(BACKFILL_COMPLETE_KEY, True)
        logger.info("Race history backfill complete — no more past races found")
        return 0

    new_records = _parse_races(races, torn, known_race_ids)

    if not new_records:
        # API returned races but none were new — we've caught up
        db.set(BACKFILL_COMPLETE_KEY, True)
        logger.info("Race history backfill complete — all past races already stored")

    return len(new_records)


@run_daily(time=(2, 0, 0))
async def torn_race_history(context: ContextTypes.DEFAULT_TYPE):
    """
    Daily watcher that collects race history from the Torn API.

    On each run it:
      1. Fetches new races (after the latest stored race).
      2. Fetches one batch of past races (before the oldest stored race)
         to gradually backfill the full history.

    Once all historical data has been retrieved the backfill step is skipped.
    Runs once per day at 2:00 AM.
    """

    db = MongoDB()
    torn: Torn = context.bot_data.get(BotData.TORN)

    if torn is None:
        return

    existing_records = RaceResult.find()
    known_race_ids = {r.race_id for r in existing_records}

    # 1. Collect new races
    new_count = await _fetch_new_races(torn, known_race_ids, existing_records)

    # 2. Backfill past races (one batch per run to stay API-friendly)
    if not db.get(BACKFILL_COMPLETE_KEY, False):
        # Re-read records so the backfill sees any just-saved new ones
        existing_records = RaceResult.find()
        known_race_ids = {r.race_id for r in existing_records}
        past_count = await _fetch_past_races(torn, known_race_ids, existing_records, db)
    else:
        past_count = 0

    total = new_count + past_count

    if total > 0:
        logger.info("Saved %d race(s) to history (new: %d, backfill: %d)", total, new_count, past_count)

        chat_id = db.get(DatabaseConstants.MAIN_CHAT_ID)
        if chat_id:
            parts = []
            if new_count:
                parts.append(f"{new_count} new")
            if past_count:
                parts.append(f"{past_count} past")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🏁 Race history updated: {' + '.join(parts)} race(s) recorded.",
            )
