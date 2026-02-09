from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict

from modules.database import Document


class RaceResult(Document):
    """Document model for storing individual race results from the user's perspective."""

    model_config = ConfigDict(collection_name="race_history")

    race_id: int
    title: str
    track_id: int
    creator_id: int
    status: str
    laps: int
    is_official: bool
    skill_gain: Optional[float] = None

    # Schedule timestamps (Unix)
    schedule_join_from: Optional[int] = None
    schedule_join_until: Optional[int] = None
    schedule_start: Optional[int] = None
    schedule_end: Optional[int] = None

    # Participants
    participants_min: Optional[int] = None
    participants_max: Optional[int] = None
    participants_current: Optional[int] = None

    # Requirements
    requirement_car_class: Optional[str] = None
    requirement_driver_class: Optional[str] = None
    requirement_car_item_id: Optional[int] = None
    requires_stock_car: Optional[bool] = None
    requires_password: Optional[bool] = None
    join_fee: Optional[int] = None

    # User's result in this race
    driver_id: Optional[int] = None
    position: Optional[int] = None
    car_id: Optional[int] = None
    car_item_id: Optional[int] = None
    car_item_name: Optional[str] = None
    car_class: Optional[str] = None
    has_crashed: Optional[bool] = None
    best_lap_time: Optional[float] = None
    race_time: Optional[float] = None
    time_ended: Optional[int] = None

    # All results stored as raw list for full history
    results: Optional[List[Dict[str, Any]]] = None

    # When this record was saved
    recorded_at: datetime
