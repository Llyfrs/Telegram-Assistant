from datetime import datetime
from typing import Self

from pydantic import ConfigDict
from geopy.distance import geodesic

from modules.database import Document


class StaticLocation(Document):
    """A named location with coordinates and radius."""

    model_config = ConfigDict(collection_name="static_locations")

    name: str
    description: str
    latitude: float
    longitude: float
    radius: float

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StaticLocation):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class LocationRecord(Document):
    """A record of time spent at a location."""

    model_config = ConfigDict(collection_name="location_history")

    location_name: str | None  # None represents traveling between locations
    entered: datetime
    exited: datetime

    # Store location details for historical reference
    location_description: str | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_radius: float | None = None

    @property
    def location(self) -> StaticLocation | None:
        """Reconstruct StaticLocation from stored data."""
        if self.location_name is None:
            return None
        return StaticLocation(
            name=self.location_name,
            description=self.location_description or "",
            latitude=self.location_latitude or 0.0,
            longitude=self.location_longitude or 0.0,
            radius=self.location_radius or 0.0,
        )

    @classmethod
    def from_location(cls, location: StaticLocation | None, entered: datetime, exited: datetime) -> Self:
        """Create a LocationRecord from a StaticLocation."""
        if location is None:
            return cls(
                location_name=None,
                entered=entered,
                exited=exited,
            )
        return cls(
            location_name=location.name,
            location_description=location.description,
            location_latitude=location.latitude,
            location_longitude=location.longitude,
            location_radius=location.radius,
            entered=entered,
            exited=exited,
        )


class LocationManager:

    def __init__(self, history_size: int = 10):
        """
        Initialize the LocationManager.
        :param history_size: Only the last `history_size` days of location history will be kept.
        """

        self.history_size = history_size

        self.last_location: tuple[float, float] | None = None
        self.last_location_timestamp: datetime | None = None

        self.current_location: LocationRecord | None = None

        self.speed: float = 0.0  # Speed in km/h

        self._load()

    def _save_current_record(self, record: LocationRecord):
        """Save a location record to the database."""
        record.save()

    def _cleanup_old_records(self):
        """Remove location records older than history_size days."""
        cutoff = datetime.now()
        old_records = LocationRecord.find()
        for record in old_records:
            if (cutoff - record.entered).days >= self.history_size:
                LocationRecord.delete_one(
                    location_name=record.location_name,
                    entered=record.entered
                )

    def _load(self):
        """Load locations from database - static locations are always fetched fresh."""
        pass  # Static locations and history are fetched on-demand from MongoDB

    @property
    def locations(self) -> list[StaticLocation]:
        """Get all static locations from database."""
        return StaticLocation.find()

    @property
    def location_history(self) -> list[LocationRecord]:
        """Get location history from database."""
        return LocationRecord.find()

    def _find_location_by_coordinates(self, latitude: float, longitude: float) -> StaticLocation | None:
        """
        Find a location by its coordinates.
        Returns the StaticLocation if found, otherwise None.
        """
        all_locations = self.locations
        matching = [
            loc for loc in all_locations
            if geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters <= loc.radius
        ]
        matching = sorted(
            matching,
            key=lambda loc: geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters
        )

        if matching:
            return matching[0]

        return None

    def record_live_location(self, latitude: float, longitude: float):
        """
        Record a live location with latitude, longitude and radius.
        """

        location = self._find_location_by_coordinates(latitude, longitude)

        # First record can't tell us that much
        if not self.last_location:
            self.last_location = (latitude, longitude)
            self.last_location_timestamp = datetime.now()

            self.current_location = LocationRecord.from_location(
                location=location,
                exited=datetime.now(),
                entered=datetime.now()
            )

            return

        time_delta = datetime.now() - self.last_location_timestamp

        if time_delta.seconds > 0:
            self.speed = geodesic(
                (latitude, longitude),
                (self.last_location[0], self.last_location[1])
            ).meters / time_delta.seconds
            # To km/h
            self.speed *= 3.6

        current_loc_name = self.current_location.location_name if self.current_location else None
        new_loc_name = location.name if location else None

        if new_loc_name != current_loc_name:
            if self.current_location:
                self.current_location.exited = datetime.now()
                self._save_current_record(self.current_location)

            self.current_location = LocationRecord.from_location(
                location=location,
                exited=datetime.now(),
                entered=datetime.now()
            )

        self.last_location = (latitude, longitude)
        self.last_location_timestamp = datetime.now()
        self._cleanup_old_records()

    def get_last_location(self) -> tuple[float, float] | None:
        """
        Get the last recorded location.
        Returns a tuple of (latitude, longitude) or None if no location is recorded.
        """

        if self.last_location:
            return self.last_location

        return None

    def get_current_location(self) -> LocationRecord | None:
        """
        Get the current location based on the last recorded coordinates.
        Returns a LocationRecord object or None if no location is recorded.
        """
        return self.current_location

    def add_static_location(self, name: str, description: str, latitude: float, longitude: float, radius: float):
        """
        Add a static location to the manager.
        """
        new_location = StaticLocation(
            name=name,
            description=description,
            latitude=latitude,
            longitude=longitude,
            radius=radius
        )
        new_location.save(key_field="name")

    def closest_location(self, latitude: float, longitude: float, k: int = 1) -> list[StaticLocation]:
        """
        Find the closest k locations to the given coordinates.
        Returns a list of StaticLocation objects.
        """
        all_locations = self.locations
        if not all_locations:
            return []

        sorted_locations = sorted(
            all_locations,
            key=lambda loc: geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters
        )

        return sorted_locations[:k]

    def get_location_history(self) -> list[LocationRecord]:
        """
        Get the location history.
        Returns a list of LocationRecord objects.
        """
        return self.location_history

    def get_static_locations(self) -> list[StaticLocation]:
        """
        Get the static locations.
        Returns a list of StaticLocation objects.
        """
        return self.locations

    def remove_static_location(self, name: str):
        """
        Remove a static location by its name.
        """
        StaticLocation.delete_one(name=name)
