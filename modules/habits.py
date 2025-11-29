"""Habit tracking module for daily check-ins."""

import re
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from pydantic import ConfigDict, Field

from modules.database import Document
from utils.logging import get_logger

logger = get_logger(__name__)


# Available color schemes for habit heatmaps
HABIT_COLORS = {
    "green": {"light": "#9be9a8", "medium": "#40c463", "dark": "#30a14e", "darker": "#216e39"},
    "blue": {"light": "#9ecae1", "medium": "#4292c6", "dark": "#2171b5", "darker": "#084594"},
    "purple": {"light": "#bcbddc", "medium": "#807dba", "dark": "#6a51a3", "darker": "#4a1486"},
    "orange": {"light": "#fdbe85", "medium": "#fd8d3c", "dark": "#e6550d", "darker": "#a63603"},
    "red": {"light": "#fcae91", "medium": "#fb6a4a", "dark": "#de2d26", "darker": "#a50f15"},
    "cyan": {"light": "#a6e1ed", "medium": "#54c4d9", "dark": "#2596be", "darker": "#0a6a8a"},
    "pink": {"light": "#f4b6c2", "medium": "#e57390", "dark": "#c74b73", "darker": "#8f2550"},
}


class Habit(Document):
    """A habit definition to track daily."""

    model_config = ConfigDict(collection_name="habits")

    habit_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    habit_type: str = "boolean"  # "boolean" or "count"
    options: Optional[list[str]] = None  # For count type: ["0", "1-2", "3-4", "5+"]
    color: str = "green"  # Color scheme for heatmap
    chat_id: int
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DailyLog(Document):
    """Daily log entry for habits."""

    model_config = ConfigDict(collection_name="daily_logs")

    date: str  # "2025-11-29" format
    chat_id: int
    habits: dict[str, str] = Field(default_factory=dict)  # {"habit_id": "yes"} or {"habit_id": "3"}
    notes: Optional[str] = None


def create_habit(
    name: str,
    chat_id: int,
    habit_type: str = "boolean",
    options: Optional[list[str]] = None,
    color: str = "green"
) -> dict:
    """
    Create a new habit to track.

    Args:
        name: Display name of the habit
        chat_id: Telegram chat ID
        habit_type: "boolean" or "count"
        options: For count type, the button options (e.g., ["0", "1-2", "3-4", "5+"])
        color: Color scheme for heatmap (green, blue, purple, orange, red, cyan, pink)

    Returns:
        Confirmation dict with habit details
    """
    if color not in HABIT_COLORS:
        color = "green"

    if habit_type == "count" and not options:
        options = ["1", "2", "3", "4", "5"]

    habit = Habit(
        name=name,
        habit_type=habit_type,
        options=options,
        color=color,
        chat_id=chat_id,
    )
    habit.save(key_field="habit_id")

    logger.info("Created habit %s for chat %s", name, chat_id)

    return {
        "status": "created",
        "habit_id": habit.habit_id,
        "name": name,
        "type": habit_type,
        "color": color,
    }


def get_active_habits(chat_id: int) -> list[Habit]:
    """Get all active habits for a user."""
    return Habit.find(chat_id=chat_id, active=True)


def get_habit_by_id(habit_id: str) -> Optional[Habit]:
    """Get a habit by its ID."""
    return Habit.find_one(habit_id=habit_id)


def deactivate_habit(habit_id: str) -> bool:
    """Deactivate a habit (soft delete)."""
    habit = Habit.find_one(habit_id=habit_id)
    if habit:
        habit.active = False
        habit.save(key_field="habit_id")
        logger.info("Deactivated habit %s", habit_id)
        return True
    return False


def get_or_create_daily_log(chat_id: int, log_date: Optional[date] = None) -> DailyLog:
    """Get or create a daily log for the given date."""
    if log_date is None:
        log_date = date.today()

    date_str = log_date.isoformat()

    existing = DailyLog.find_one(chat_id=chat_id, date=date_str)
    if existing:
        return existing

    log = DailyLog(
        date=date_str,
        chat_id=chat_id,
    )
    log.save()
    return log


def update_daily_log(
    chat_id: int,
    log_date: Optional[date] = None,
    habit_id: Optional[str] = None,
    habit_value: Optional[str] = None,
) -> DailyLog:
    """Update a daily log with habit completion."""
    log = get_or_create_daily_log(chat_id, log_date)

    if habit_id and habit_value is not None:
        log.habits[habit_id] = habit_value

    # Use date + chat_id as compound key for upsert
    DailyLog._collection().update_one(
        {"date": log.date, "chat_id": log.chat_id},
        {"$set": log.model_dump(mode="json")},
        upsert=True
    )

    return log


def get_logs_for_period(chat_id: int, start_date: date, end_date: date) -> list[DailyLog]:
    """Get all daily logs for a date range."""
    all_logs = DailyLog.find(chat_id=chat_id)
    
    return [
        log for log in all_logs
        if start_date.isoformat() <= log.date <= end_date.isoformat()
    ]


def _parse_numeric_value(value: str) -> Optional[float]:
    """
    Try to extract a numeric value from a habit value string.
    
    Handles formats like:
    - "3" -> 3.0
    - "1-2" -> 1.5 (midpoint)
    - "4+" -> 4.0
    - "5+" -> 5.0
    - "yes" -> 1.0
    - "no" -> 0.0
    """
    if value is None:
        return None
    
    value = value.strip().lower()
    
    # Boolean values
    if value in ("yes", "true"):
        return 1.0
    if value in ("no", "false"):
        return 0.0
    
    # Try direct numeric
    try:
        return float(value)
    except ValueError:
        pass
    
    # Handle "4+" style
    if value.endswith("+"):
        try:
            return float(value[:-1])
        except ValueError:
            pass
    
    # Handle "1-2" range style (take midpoint)
    range_match = re.match(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", value)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2
    
    return None


def _get_trend(values: list[float], split_point: int) -> tuple[str, float]:
    """
    Calculate trend by comparing first half to second half averages.
    Returns (trend_symbol, change).
    """
    if len(values) < 4:
        return "→", 0.0
    
    first_half = values[:split_point]
    second_half = values[split_point:]
    
    if not first_half or not second_half:
        return "→", 0.0
    
    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    
    change = second_avg - first_avg
    
    if change > 0.2:
        return "↗️", change
    elif change < -0.2:
        return "↘️", change
    else:
        return "→", change


def get_habit_stats(habit_id: str, days: int = 30) -> dict:
    """
    Get statistics for a habit over the last N days.
    
    For boolean habits: streaks, completion rate
    For count habits: average, trend, distribution, min/max
    """
    habit = get_habit_by_id(habit_id)
    if not habit:
        return {"error": "Habit not found"}

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    logs = get_logs_for_period(habit.chat_id, start_date, end_date)
    logs_by_date = {log.date: log for log in logs}

    # Collect all values
    values = []  # (date_str, raw_value, numeric_value)
    
    for i in range(days):
        check_date = (start_date + timedelta(days=i)).isoformat()
        log = logs_by_date.get(check_date)
        
        if log and habit.habit_id in log.habits:
            raw_value = log.habits[habit.habit_id]
            numeric = _parse_numeric_value(raw_value)
            values.append((check_date, raw_value, numeric))

    days_logged = len(values)
    
    if habit.habit_type == "boolean":
        return _get_boolean_stats(habit, values, days)
    else:
        return _get_count_stats(habit, values, days)


def _get_boolean_stats(habit: Habit, values: list, total_days: int) -> dict:
    """Get stats for a boolean habit."""
    completed = 0
    current_streak = 0
    max_streak = 0
    temp_streak = 0
    
    # Sort by date
    values_sorted = sorted(values, key=lambda x: x[0])
    
    for date_str, raw_value, numeric in values_sorted:
        if raw_value.lower() in ("yes", "true", "1"):
            completed += 1
            temp_streak += 1
            max_streak = max(max_streak, temp_streak)
        else:
            temp_streak = 0
    
    current_streak = temp_streak
    days_logged = len(values)
    
    return {
        "habit_name": habit.name,
        "habit_type": "boolean",
        "days_in_period": total_days,
        "days_logged": days_logged,
        "days_completed": completed,
        "completion_rate": f"{(completed / total_days * 100):.1f}%" if total_days > 0 else "0%",
        "current_streak": current_streak,
        "max_streak": max_streak,
    }


def _get_count_stats(habit: Habit, values: list, total_days: int) -> dict:
    """Get stats for a count/numeric habit with rich analytics."""
    days_logged = len(values)
    
    if days_logged == 0:
        return {
            "habit_name": habit.name,
            "habit_type": "count",
            "days_in_period": total_days,
            "days_logged": 0,
            "message": "No data logged yet.",
        }
    
    # Extract numeric values (filter out None)
    numeric_values = [v[2] for v in values if v[2] is not None]
    raw_values = [v[1] for v in values]
    dates = [v[0] for v in values]
    
    if not numeric_values:
        # Can't compute numeric stats, just show distribution
        distribution = {}
        for raw in raw_values:
            distribution[raw] = distribution.get(raw, 0) + 1
        
        return {
            "habit_name": habit.name,
            "habit_type": "count",
            "days_in_period": total_days,
            "days_logged": days_logged,
            "log_rate": f"{(days_logged / total_days * 100):.1f}%",
            "distribution": distribution,
        }
    
    # Calculate statistics
    avg = sum(numeric_values) / len(numeric_values)
    min_val = min(numeric_values)
    max_val = max(numeric_values)
    
    # Find min/max dates
    min_idx = numeric_values.index(min_val)
    max_idx = numeric_values.index(max_val)
    min_date = dates[min_idx]
    max_date = dates[max_idx]
    
    # Trend
    split = len(numeric_values) // 2
    trend_symbol, trend_change = _get_trend(numeric_values, split)
    
    # Distribution of raw values
    distribution = {}
    for raw in raw_values:
        distribution[raw] = distribution.get(raw, 0) + 1
    
    # Sort distribution by trying to parse keys numerically
    def sort_key(item):
        val = _parse_numeric_value(item[0])
        return val if val is not None else float('inf')
    
    sorted_dist = dict(sorted(distribution.items(), key=sort_key))
    
    # Determine the scale (max possible value from options)
    scale_max = None
    if habit.options:
        for opt in reversed(habit.options):
            parsed = _parse_numeric_value(opt)
            if parsed is not None:
                scale_max = parsed
                break
    
    result = {
        "habit_name": habit.name,
        "habit_type": "count",
        "days_in_period": total_days,
        "days_logged": days_logged,
        "log_rate": f"{(days_logged / total_days * 100):.1f}%",
        "average": round(avg, 2),
        "trend": trend_symbol,
        "trend_change": round(trend_change, 2),
        "min_value": min_val,
        "min_date": min_date,
        "max_value": max_val,
        "max_date": max_date,
        "distribution": sorted_dist,
    }
    
    if scale_max:
        result["scale_max"] = scale_max
        result["average_display"] = f"{avg:.1f}/{scale_max}"
    
    return result


def format_habit_stats(stats: dict) -> str:
    """Format habit stats as a readable string."""
    if "error" in stats:
        return stats["error"]
    
    if "message" in stats:
        return f"**{stats['habit_name']}** ({stats['days_in_period']} days)\n{stats['message']}"
    
    lines = [f"**{stats['habit_name']}** (last {stats['days_in_period']} days)"]
    lines.append("━" * 20)
    
    if stats["habit_type"] == "boolean":
        lines.append(f"📊 Completed: {stats['days_completed']}/{stats['days_in_period']} ({stats['completion_rate']})")
        lines.append(f"🔥 Current streak: {stats['current_streak']} days")
        lines.append(f"🏆 Best streak: {stats['max_streak']} days")
    else:
        # Count type
        avg_display = stats.get("average_display", f"{stats['average']}")
        lines.append(f"📊 Average: {avg_display}")
        lines.append(f"📈 Trend: {stats['trend']} ({stats['trend_change']:+.2f})")
        lines.append(f"📅 Logged: {stats['days_logged']}/{stats['days_in_period']} days ({stats['log_rate']})")
        lines.append("")
        lines.append("Distribution:")
        
        # Build ASCII bar chart
        dist = stats.get("distribution", {})
        max_count = max(dist.values()) if dist else 1
        
        for value, count in dist.items():
            bar_len = int((count / max_count) * 10)
            bar = "█" * bar_len
            pct = (count / stats['days_logged'] * 100) if stats['days_logged'] > 0 else 0
            lines.append(f"  {value}: {bar} {count} ({pct:.0f}%)")
        
        lines.append("")
        lines.append(f"🔝 Best: {stats['max_value']} on {stats['max_date']}")
        lines.append(f"🔻 Lowest: {stats['min_value']} on {stats['min_date']}")
    
    return "\n".join(lines)
