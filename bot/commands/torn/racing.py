"""Show racing skill statistics and predictions."""

import io
from datetime import datetime, timedelta
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from telegram import Update
from telegram.ext import ContextTypes

from bot.classes.command import command
from bot.watchers.torn_racing_skill import RacingSkillRecord
from utils.logging import get_logger

logger = get_logger(__name__)


def calculate_predictions(records: list[RacingSkillRecord]) -> dict:
    """
    Calculate racing skill predictions based on historical data.
    
    Models diminishing returns where skill gains decrease as skill level increases.
    Uses the formula: gain_rate = k * (100 - skill)^n
    """
    if len(records) < 2:
        return None

    # Sort records by time
    sorted_records = sorted(records, key=lambda r: r.recorded_at)
    
    # Extract gains with their skill levels (for diminishing returns analysis)
    gains_data = []
    for record in sorted_records:
        if record.gain is not None and record.gain > 0:
            # Skill level before this gain
            prev_skill = record.skill - record.gain
            gains_data.append({
                'skill_before': prev_skill,
                'gain': record.gain,
                'time': record.recorded_at
            })
    
    if len(gains_data) < 2:
        return None

    current_skill = sorted_records[-1].skill
    first_record = sorted_records[0]
    last_record = sorted_records[-1]
    
    # Calculate time span and total gains
    time_span = (last_record.recorded_at - first_record.recorded_at).total_seconds()
    if time_span <= 0:
        return None
    
    total_gains = sum(g['gain'] for g in gains_data)
    num_gains = len(gains_data)
    
    # Average gain per event
    avg_gain_per_event = total_gains / num_gains if num_gains > 0 else 0
    
    # Calculate gains rate (events per day)
    days_elapsed = time_span / 86400
    events_per_day = num_gains / days_elapsed if days_elapsed > 0 else 0
    
    # Recent gains (last 24 hours)
    now = datetime.utcnow()
    recent_gains = [g for g in gains_data if (now - g['time']).total_seconds() < 86400]
    recent_avg = sum(g['gain'] for g in recent_gains) / len(recent_gains) if recent_gains else avg_gain_per_event
    
    # Fit diminishing returns model: gain = k * (100 - skill)^n
    # Use linear regression on log-transformed data
    try:
        skill_remaining = [100 - g['skill_before'] for g in gains_data if g['skill_before'] < 99]
        gains = [g['gain'] for g in gains_data if g['skill_before'] < 99]
        
        if len(skill_remaining) >= 2 and all(s > 0 for s in skill_remaining) and all(g > 0 for g in gains):
            log_remaining = np.log(skill_remaining)
            log_gains = np.log(gains)
            
            # Linear regression: log(gain) = log(k) + n * log(100 - skill)
            n, log_k = np.polyfit(log_remaining, log_gains, 1)
            k = np.exp(log_k)
            
            # Clamp n to reasonable range (0.5 to 2.0 for typical diminishing returns)
            n = max(0.5, min(2.0, n))
        else:
            # Fallback: assume linear diminishing returns
            k = avg_gain_per_event / max(1, 100 - current_skill)
            n = 1.0
    except Exception as e:
        logger.debug("Could not fit diminishing returns model: %s", e)
        k = avg_gain_per_event / max(1, 100 - current_skill)
        n = 1.0

    def predict_gain_at_skill(skill: float) -> float:
        """Predict gain per event at a given skill level."""
        remaining = max(0.01, 100 - skill)
        return k * (remaining ** n)

    def predict_skill_after_days(days: float, start_skill: float) -> float:
        """Simulate skill progression over given days."""
        skill = start_skill
        events = int(events_per_day * days)
        
        for _ in range(events):
            if skill >= 100:
                break
            gain = predict_gain_at_skill(skill)
            # Add some variance (skill gains have randomness)
            skill = min(100, skill + gain)
        
        return skill

    def predict_days_to_target(target: float, start_skill: float, max_days: int = 3650) -> Optional[float]:
        """Estimate days to reach target skill."""
        if start_skill >= target:
            return 0
        
        skill = start_skill
        days = 0
        daily_events = max(1, int(events_per_day))
        
        while skill < target and days < max_days:
            for _ in range(daily_events):
                if skill >= target:
                    break
                gain = predict_gain_at_skill(skill)
                skill = min(100, skill + gain)
            days += 1
        
        return days if skill >= target else None

    # Calculate predictions
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
        'sorted_records': sorted_records,
        'predict_skill_after_days': predict_skill_after_days,
    }


def generate_graph(predictions: dict) -> io.BytesIO:
    """Generate a racing skill progression graph with predictions."""
    
    # Set up the plot with a dark theme
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Configure colors
    bg_color = '#1a1a2e'
    grid_color = '#2d2d44'
    history_color = '#00d4ff'
    prediction_color = '#ff6b35'
    target_color = '#4ade80'
    marker_color = '#fbbf24'
    
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    sorted_records = predictions['sorted_records']
    predict_func = predictions['predict_skill_after_days']
    current_skill = predictions['current_skill']
    
    # Historical data
    dates = [r.recorded_at for r in sorted_records]
    skills = [r.skill for r in sorted_records]
    
    ax.plot(dates, skills, color=history_color, linewidth=2, label='Historical', marker='o', markersize=3)
    
    # Generate prediction curve
    now = datetime.utcnow()
    max_pred_days = 400  # Show up to ~13 months
    
    pred_dates = []
    pred_skills = []
    
    for day in range(0, max_pred_days + 1, 1):
        pred_dates.append(now + timedelta(days=day))
        pred_skills.append(predict_func(day, current_skill))
    
    ax.plot(pred_dates, pred_skills, color=prediction_color, linewidth=2, linestyle='--', label='Predicted', alpha=0.8)
    
    # Target line at 100
    ax.axhline(y=100, color=target_color, linestyle=':', linewidth=1.5, label='Target (100)', alpha=0.7)
    
    # Mark prediction points (7d, 30d, 1y)
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
    
    # Mark when reaching 100
    if predictions['days_to_100'] and predictions['days_to_100'] <= max_pred_days:
        target_date = predictions['date_to_100']
        ax.scatter([target_date], [100], color=target_color, s=150, zorder=5, marker='*', edgecolors='white', linewidths=1)
        ax.annotate(f'🏁 100!\n{target_date.strftime("%b %d")}', (target_date, 100),
                   textcoords="offset points", xytext=(0, -25),
                   ha='center', fontsize=9, color=target_color, fontweight='bold')
    
    # Styling
    ax.set_xlabel('Date', fontsize=11, color='white')
    ax.set_ylabel('Racing Skill', fontsize=11, color='white')
    ax.set_title('🏎️ Racing Skill Progression & Predictions', fontsize=14, color='white', fontweight='bold', pad=15)
    
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, color=grid_color)
    ax.legend(loc='lower right', facecolor=bg_color, edgecolor=grid_color)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)
    
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color(grid_color)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=bg_color, edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    
    return buf


@command
async def racing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show racing skill statistics and predictions."""
    
    # Get all records
    records = RacingSkillRecord.find()
    
    if not records:
        await update.message.reply_text(
            "🏎️ No racing skill data recorded yet.\n"
            "Start racing and the tracker will begin recording your progress!"
        )
        return
    
    if len(records) < 2:
        current = records[0].skill
        await update.message.reply_text(
            f"🏎️ **Racing Skill**\n\n"
            f"Current: **{current:.4f}**\n\n"
            f"_Not enough data for predictions yet. Keep racing!_",
            parse_mode="Markdown"
        )
        return
    
    predictions = calculate_predictions(records)
    
    if predictions is None:
        await update.message.reply_text(
            "🏎️ Could not calculate predictions. Need more data points."
        )
        return
    
    # Build message
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
    
    # Generate and send graph
    try:
        graph = generate_graph(predictions)
        await update.message.reply_photo(
            photo=graph,
            caption=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Failed to generate racing graph: %s", e)
        # Fall back to text only
        await update.message.reply_text(message, parse_mode="Markdown")

