"""Generate GitHub-style heatmap visualizations for habit tracking."""

import re
from datetime import date, timedelta
from io import BytesIO
from typing import Optional

import matplotlib

# This module generates images in-memory and is often invoked from background worker threads
# (e.g., Telegram bot handlers). For stability, force a non-GUI backend.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from modules.habits import (
    DailyLog,
    get_logs_for_period,
    get_habit_by_id,
    HABIT_COLORS,
)
from utils.logging import get_logger

logger = get_logger(__name__)


def _parse_period(period: str) -> tuple[date, date, str]:
    """
    Parse period string into start/end dates and title suffix.
    
    Formats:
        - "last_30_days" -> last 30 days
        - "last_365_days" -> last 365 days
        - "month:2025-11" -> specific month
        - "year:2025" -> specific year
    """
    today = date.today()

    if period == "last_30_days":
        return today - timedelta(days=29), today, "Last 30 Days"
    
    elif period == "last_365_days":
        return today - timedelta(days=364), today, "Last 365 Days"
    
    elif period.startswith("month:"):
        # Format: month:2025-11
        year, month = map(int, period[6:].split("-"))
        start = date(year, month, 1)
        # Get last day of month
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        month_name = start.strftime("%B %Y")
        return start, end, month_name
    
    elif period.startswith("year:"):
        year = int(period[5:])
        return date(year, 1, 1), date(year, 12, 31), str(year)
    
    else:
        # Default to last 30 days
        return today - timedelta(days=29), today, "Last 30 Days"


def _get_color_scale(base_color: str, value: float) -> str:
    """Get color based on value (0-1 scale) and base color scheme."""
    colors = HABIT_COLORS.get(base_color, HABIT_COLORS["green"])
    
    if value <= 0:
        return "#ebedf0"  # Empty/gray
    elif value <= 0.25:
        return colors["light"]
    elif value <= 0.5:
        return colors["medium"]
    elif value <= 0.75:
        return colors["dark"]
    else:
        return colors["darker"]


def _parse_numeric_value(value: str) -> Optional[float]:
    """
    Try to extract a numeric value from a habit value string.
    Handles: "3", "1-2" (midpoint), "4+", "yes", "no"
    """
    if value is None:
        return None
    
    value = value.strip().lower()
    
    if value in ("yes", "true"):
        return 1.0
    if value in ("no", "false"):
        return 0.0
    
    try:
        return float(value)
    except ValueError:
        pass
    
    if value.endswith("+"):
        try:
            return float(value[:-1])
        except ValueError:
            pass
    
    range_match = re.match(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", value)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2
    
    return None


def _habit_value_to_intensity(habit, value: Optional[str]) -> float:
    """Convert habit value to 0-1 intensity for heatmap."""
    if value is None:
        return 0.0
    
    if habit.habit_type == "boolean":
        return 1.0 if value.lower() in ("yes", "true", "1") else 0.0
    
    elif habit.habit_type == "count" and habit.options:
        # For count habits, normalize by position in options list
        try:
            idx = habit.options.index(value)
            return (idx + 1) / len(habit.options)
        except ValueError:
            # If exact match fails, try to parse numerically and normalize
            numeric = _parse_numeric_value(value)
            if numeric is not None and habit.options:
                # Find max value from options
                max_val = 1.0
                for opt in reversed(habit.options):
                    parsed = _parse_numeric_value(opt)
                    if parsed is not None:
                        max_val = parsed
                        break
                return min(1.0, numeric / max_val) if max_val > 0 else 0.0
            return 0.0
    
    return 0.0


def generate_habit_heatmap(
    habit_id: str,
    period: str = "last_30_days",
) -> Optional[BytesIO]:
    """
    Generate a GitHub-style heatmap for a habit.
    
    Args:
        habit_id: The habit to visualize
        period: Time period (last_30_days, last_365_days, month:YYYY-MM, year:YYYY)
    
    Returns:
        BytesIO buffer containing PNG image, or None on error
    """
    habit = get_habit_by_id(habit_id)
    if not habit:
        logger.error("Habit not found: %s", habit_id)
        return None

    start_date, end_date, period_label = _parse_period(period)
    logs = get_logs_for_period(start_date, end_date)
    logs_by_date = {log.date: log for log in logs}

    return _render_heatmap(
        title=f"{habit.name} - {period_label}",
        start_date=start_date,
        end_date=end_date,
        logs_by_date=logs_by_date,
        value_extractor=lambda log: _habit_value_to_intensity(
            habit, log.habits.get(habit.habit_id) if log else None
        ),
        color=habit.color,
    )


def _render_heatmap(
    title: str,
    start_date: date,
    end_date: date,
    logs_by_date: dict[str, DailyLog],
    value_extractor: callable,
    color: str,
) -> BytesIO:
    """
    Render a GitHub-style contribution heatmap.
    
    Layout: 7 rows (Mon-Sun), columns = weeks
    """
    # Find the Monday before or on start_date
    days_since_monday = start_date.weekday()
    grid_start = start_date - timedelta(days=days_since_monday)
    
    # Find the Sunday after or on end_date
    days_until_sunday = (6 - end_date.weekday()) % 7
    grid_end = end_date + timedelta(days=days_until_sunday)
    
    total_grid_days = (grid_end - grid_start).days + 1
    num_weeks = total_grid_days // 7

    # Build color grid (7 rows x num_weeks columns)
    colors_grid = [["#ebedf0" for _ in range(num_weeks)] for _ in range(7)]

    for week in range(num_weeks):
        for day in range(7):
            current_date = grid_start + timedelta(days=week * 7 + day)
            
            if current_date < start_date or current_date > end_date:
                colors_grid[day][week] = "#f6f8fa"  # Outside range - very light
                continue

            date_str = current_date.isoformat()
            log = logs_by_date.get(date_str)
            intensity = value_extractor(log)
            colors_grid[day][week] = _get_color_scale(color, intensity)

    # Create figure
    fig_width = max(6, num_weeks * 0.4)
    fig, ax = plt.subplots(figsize=(fig_width, 3))
    
    # Set dark background for better contrast
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')

    # Draw squares
    square_size = 0.85

    for week in range(num_weeks):
        for day in range(7):
            rect = mpatches.FancyBboxPatch(
                (week, 6 - day),
                square_size,
                square_size,
                boxstyle="round,pad=0.02,rounding_size=0.1",
                facecolor=colors_grid[day][week],
                edgecolor='none',
            )
            ax.add_patch(rect)

    # Configure axes
    ax.set_xlim(-0.5, num_weeks + 0.5)
    ax.set_ylim(-0.5, 7.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # Add title
    ax.set_title(title, fontsize=14, fontweight='bold', color='white', pad=10)

    # Add day labels
    day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i, label in enumerate(day_labels):
        # y-coordinate: 6 - i (since 0 is Mon at top, but grid is plotted bottom-up so 6 is top)
        # day=0 (Mon) -> y=6. day=6 (Sun) -> y=0.
        ax.text(-0.8, 6 - i + 0.4, label, fontsize=8, color='#8b949e', 
               ha='right', va='center')

    # Add month labels for longer periods
    if num_weeks > 8:
        current_month = None
        for week in range(num_weeks):
            week_date = grid_start + timedelta(days=week * 7)
            if week_date.month != current_month and week_date >= start_date:
                current_month = week_date.month
                ax.text(week + 0.4, 7.3, week_date.strftime('%b'), 
                       fontsize=8, color='#8b949e', ha='center')

    # Add legend
    legend_colors = HABIT_COLORS.get(color, HABIT_COLORS["green"])
    legend_items = [
        ("#ebedf0", "None"),
        (legend_colors["light"], "Low"),
        (legend_colors["medium"], "Med"),
        (legend_colors["dark"], "High"),
        (legend_colors["darker"], "Full"),
    ]
    
    # Calculate legend position (bottom right)
    legend_x = num_weeks - 4.5
    
    for i, (col, _) in enumerate(legend_items):
        rect = mpatches.FancyBboxPatch(
            (legend_x + i * 0.5, -1.1),
            0.4, 0.4,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=col,
            edgecolor='none',
        )
        ax.add_patch(rect)

    plt.tight_layout()

    # Save to BytesIO buffer
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', 
                facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)

    logger.info("Generated heatmap: %s", title)
    return buf
