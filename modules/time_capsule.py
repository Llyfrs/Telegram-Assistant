"""Time Capsule module for sending messages to your future self."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from pydantic import ConfigDict, Field

from modules.database import Document


class TimeCapsule(Document):
    """A message to be delivered to the user at a future date."""

    model_config = ConfigDict(collection_name="time_capsules")

    capsule_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    message: str
    delivery_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent: bool = False
    chat_id: int


def create_capsule(message: str, deliver_in_days: int, chat_id: int) -> dict:
    """
    Create a time capsule to be delivered in the future.

    Args:
        message: The message to send to future self
        deliver_in_days: Number of days from now to deliver
        chat_id: Telegram chat ID to deliver to

    Returns:
        Confirmation dict with capsule details
    """
    delivery_date = datetime.utcnow() + timedelta(days=deliver_in_days)

    capsule = TimeCapsule(
        message=message,
        delivery_date=delivery_date,
        chat_id=chat_id,
    )
    capsule.save(key_field="capsule_id")

    return {
        "status": "created",
        "capsule_id": capsule.capsule_id,
        "delivery_date": delivery_date.strftime("%Y-%m-%d"),
        "days_until_delivery": deliver_in_days,
    }


def get_pending_capsules() -> list[TimeCapsule]:
    """Get all capsules that are due for delivery."""
    now = datetime.utcnow()
    # Find all unsent capsules where delivery_date has passed
    all_unsent = TimeCapsule.find(sent=False)
    return [c for c in all_unsent if c.delivery_date <= now]


def mark_as_sent(capsule_id: str) -> None:
    """Mark a capsule as sent."""
    capsule = TimeCapsule.find_one(capsule_id=capsule_id)
    if capsule:
        capsule.sent = True
        capsule.save(key_field="capsule_id")


def get_user_capsules(chat_id: int, include_sent: bool = False) -> list[TimeCapsule]:
    """Get all capsules for a specific user."""
    if include_sent:
        return TimeCapsule.find(chat_id=chat_id)
    return TimeCapsule.find(chat_id=chat_id, sent=False)


def cancel_capsule(capsule_id: str) -> bool:
    """Cancel a pending capsule."""
    capsule = TimeCapsule.find_one(capsule_id=capsule_id, sent=False)
    if capsule:
        TimeCapsule.delete_one(capsule_id=capsule_id)
        return True
    return False

