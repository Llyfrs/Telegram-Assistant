"""Show racing skill statistics and predictions using collected race history."""

import io
from datetime import datetime, timedelta
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from telegram import Update
from telegram.ext import ContextTypes

from bot.classes.command import command
from enums.bot_data import BotData
from modules.torn import Torn
from structures.race_record import RaceResult
from utils.logging import get_logger

logger = get_logger(__name__)


def _build_skill_timeline(races: list[RaceResult], current_skill: float) -> list[dict]:
    """
    Reconstruct a skill timeline from race history and the current skill level.

    Races with a ``skill_gain`` are sorted newest-first and we walk backwards,
    subtracting each gain from the running skill to deduce the level at that
    point.  The result is returned sorted oldest-first.
    """
    races_with_gain = [r for r in races if r.skill_gain is not None and r.skill_gain > 0]

    if not races_with_gain:
        return []

    # Sort newest first so we can subtract gains starting from current_skill
    races_with_gain.sort(
        key=lambda r: r.schedule_end if r.schedule_end is not None else r.recorded_at.timestamp(),
        reverse=True,
    )

    timeline = []
    skill = current_skill
    for race in races_with_gain:
        race_time = datetime.utcfromtimestamp(race.schedule_end) if race.schedule_end else race.recorded_at
        timeline.append({
            'skill': skill,
            'gain': race.skill_gain,
            'skill_before': skill - race.skill_gain,
            'time': race_time,
            'race': race,
        })
        skill -= race.skill_gain

    # Return in chronological order
    timeline.reverse()
    return timeline


def calculate_predictions(timeline: list[dict], current_skill: float) -> Optional[dict]:
    """
    Calculate racing skill predictions based on race-history data.

    Models diminishing returns where skill gains decrease as skill level
    increases.  Uses the formula: gain_rate = k * (100 - skill)^n

    Many factors influence gain (laps, map, number of participants, official
    status which gives ~2× bonus, finishing position) but the exact formula is
    unknown, so we fit a simple power-law model on the observed data.
    """
    if len(timeline) < 2:
        return None

    first = timeline[0]
    last = timeline[-1]

    # Time span covered by the data
    time_span = (last['time'] - first['time']).total_seconds()
    if time_span <= 0:
        return None

    total_gains = sum(p['gain'] for p in timeline)
    num_gains = len(timeline)

    avg_gain_per_event = total_gains / num_gains if num_gains > 0 else 0

    days_elapsed = time_span / 86400
    events_per_day = num_gains / days_elapsed if days_elapsed > 0 else 0

    # Recent gains (last 24 hours)
    now = datetime.utcnow()
    recent = [p for p in timeline if (now - p['time']).total_seconds() < 86400]
    recent_avg = sum(p['gain'] for p in recent) / len(recent) if recent else avg_gain_per_event

    # Fit diminishing returns model: gain = k * (100 - skill)^n
    try:
        skill_remaining = [100 - p['skill_before'] for p in timeline if p['skill_before'] < 99]
        gains = [p['gain'] for p in timeline if p['skill_before'] < 99]

        if len(skill_remaining) >= 2 and all(s > 0 for s in skill_remaining) and all(g > 0 for g in gains):
            log_remaining = np.log(skill_remaining)
            log_gains = np.log(gains)

            n, log_k = np.polyfit(log_remaining, log_gains, 1)
            k = np.exp(log_k)

            n = max(0.5, min(2.0, n))
        else:
            k = avg_gain_per_event / max(1, 100 - current_skill)
            n = 1.0
    except Exception as e:
        logger.debug("Could not fit diminishing returns model: %s", e)
        k = avg_gain_per_event / max(1, 100 - current_skill)
        n = 1.0

    def predict_gain_at_skill(skill: float) -> float:
        remaining = max(0.01, 100 - skill)
        return k * (remaining ** n)

    def predict_skill_after_days(days: float, start_skill: float) -> float:
        skill = start_skill
        events = int(events_per_day * days)
        for _ in range(events):
            if skill >= 100:
                break
            skill = min(100, skill + predict_gain_at_skill(skill))
        return skill

    def predict_days_to_target(target: float, start_skill: float, max_days: int = 3650) -> Optional[float]:
        if start_skill >= target:
            return 0
        skill = start_skill
        days = 0
        daily_events = max(1, int(events_per_day))
        while skill < target and days < max_days:
            for _ in range(daily_events):
                if skill >= target:
                    break
                skill = min(100, skill + predict_gain_at_skill(skill))
            days += 1
        return days if skill >= target else None

    days_to_100 = predict_days_to_target(100, current_skill)
    skill_7d = predict_skill_after_days(7, current_skill)
    skill_30d = predict_skill_after_days(30, current_skill)
    skill_365d = predict_skill_after_days(365, current_skill)

    return {
        'current_skill': current_skill,
        'total_gains': total_gains,
        'avg_gain': avg_gain_per_event,
        'recent_avg': recent_avg,
        'events_per_day': events_per_day,
        'days_to_100': days_to_100,
        'date_to_100': (now + timedelta(days=days_to_100)) if days_to_100 else None,
        'skill_7d': skill_7d,
        'skill_30d': skill_30d,
        'skill_365d': skill_365d,
        'model_k': k,
        'model_n': n,
        'timeline': timeline,
        'predict_skill_after_days': predict_skill_after_days,
    }


def generate_graph(predictions: dict) -> io.BytesIO:
    """Generate a racing skill progression graph with predictions."""

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))

    bg_color = '#1a1a2e'
    grid_color = '#2d2d44'
    history_color = '#00d4ff'
    prediction_color = '#ff6b35'
    target_color = '#4ade80'
    marker_color = '#fbbf24'

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    timeline = predictions['timeline']
    predict_func = predictions['predict_skill_after_days']
    current_skill = predictions['current_skill']

    # Historical data — plot skill *after* each race
    dates = [p['time'] for p in timeline]
    skills = [p['skill'] for p in timeline]

    ax.plot(dates, skills, color=history_color, linewidth=2, label='Historical', marker='o', markersize=3)

    # Prediction curve
    now = datetime.utcnow()
    max_pred_days = 400

    pred_dates = [now + timedelta(days=d) for d in range(max_pred_days + 1)]
    pred_skills = [predict_func(d, current_skill) for d in range(max_pred_days + 1)]

    ax.plot(pred_dates, pred_skills, color=prediction_color, linewidth=2, linestyle='--', label='Predicted', alpha=0.8)

    ax.axhline(y=100, color=target_color, linestyle=':', linewidth=1.5, label='Target (100)', alpha=0.7)

    markers = [
        (7, predictions['skill_7d'], '7d'),
        (30, predictions['skill_30d'], '30d'),
        (365, predictions['skill_365d'], '1y'),
    ]

    for days, skill, label in markers:
        if days <= max_pred_days:
            marker_date = now + timedelta(days=days)
            ax.scatter([marker_date], [skill], color=marker_color, s=100, zorder=5, edgecolors='white', linewidths=1)
            ax.annotate(f'{label}\n{skill:.1f}', (marker_date, skill),
                       textcoords="offset points", xytext=(0, 15),
                       ha='center', fontsize=9, color=marker_color, fontweight='bold')

    if predictions['days_to_100'] and predictions['days_to_100'] <= max_pred_days:
        target_date = predictions['date_to_100']
        ax.scatter([target_date], [100], color=target_color, s=150, zorder=5, marker='*', edgecolors='white', linewidths=1)
        ax.annotate(f'🏁 100!\n{target_date.strftime("%b %d")}', (target_date, 100),
                   textcoords="offset points", xytext=(0, -25),
                   ha='center', fontsize=9, color=target_color, fontweight='bold')

    ax.set_xlabel('Date', fontsize=11, color='white')
    ax.set_ylabel('Racing Skill', fontsize=11, color='white')
    ax.set_title('🏎️ Racing Skill Progression & Predictions', fontsize=14, color='white', fontweight='bold', pad=15)

    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, color=grid_color)
    ax.legend(loc='lower right', facecolor=bg_color, edgecolor=grid_color)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)

    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color(grid_color)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=bg_color, edgecolor='none')
    buf.seek(0)
    plt.close(fig)

    return buf


@command
async def racing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show racing skill statistics and predictions."""

    torn: Torn = context.bot_data.get(BotData.TORN)
    if torn is None:
        await update.message.reply_text("🏎️ Torn API is not configured.")
        return

    # Fetch current skill from the API
    user = await torn.get_user()
    if user is None or user.get("racing") is None:
        await update.message.reply_text("🏎️ Could not fetch current racing skill from Torn API.")
        return

    current_skill = float(user["racing"])

    # Build timeline from collected race history
    races = RaceResult.find()
    timeline = _build_skill_timeline(races, current_skill)

    if not timeline:
        await update.message.reply_text(
            f"🏎️ **Racing Skill**\n\n"
            f"Current: **{current_skill:.4f}**\n\n"
            f"_No race history with skill gains recorded yet. "
            f"Race history is collected automatically — keep racing!_",
            parse_mode="Markdown"
        )
        return

    if len(timeline) < 2:
        await update.message.reply_text(
            f"🏎️ **Racing Skill**\n\n"
            f"Current: **{current_skill:.4f}**\n\n"
            f"_Not enough data for predictions yet. Keep racing!_",
            parse_mode="Markdown"
        )
        return

    predictions = calculate_predictions(timeline, current_skill)

    if predictions is None:
        await update.message.reply_text(
            "🏎️ Could not calculate predictions. Need more data points."
        )
        return

    current = predictions['current_skill']
    total = predictions['total_gains']
    avg = predictions['avg_gain']
    recent = predictions['recent_avg']
    epd = predictions['events_per_day']

    message = (
        f"🏎️ **Racing Skill Statistics**\n\n"
        f"**Current:** {current:.4f}\n"
        f"**Total gained (tracked):** +{total:.4f}\n\n"
        f"📈 **Gain Rate**\n"
        f"Average: {avg:.4f}/race\n"
        f"Recent (24h): {recent:.4f}/race\n"
        f"Races/day: ~{epd:.0f}\n\n"
        f"🔮 **Predictions**\n"
    )

    if predictions['days_to_100']:
        days = predictions['days_to_100']
        date = predictions['date_to_100']
        message += f"Skill 100: ~{days:.0f} days ({date.strftime('%b %d, %Y')})\n"
    else:
        message += "Skill 100: >10 years\n"

    message += (
        f"In 7 days: {predictions['skill_7d']:.2f}\n"
        f"In 30 days: {predictions['skill_30d']:.2f}\n"
        f"In 1 year: {predictions['skill_365d']:.2f}"
    )

    try:
        graph = generate_graph(predictions)
        await update.message.reply_photo(
            photo=graph,
            caption=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Failed to generate racing graph: %s", e)
        await update.message.reply_text(message, parse_mode="Markdown")

