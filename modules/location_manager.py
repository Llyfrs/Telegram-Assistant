from dataclasses import dataclass
from datetime import datetime

from modules.database import ValkeyDB
from enums.database import DatabaseConstants
from geopy.distance import geodesic

@dataclass
class StaticLocation:
    name: str
    description: str
    latitude: float
    longitude: float
    radius: float

@dataclass()
class LocationRecord:
    location: StaticLocation | None  # None represents a undefined location (usually while traveling between locations)
    exited: datetime
    entered: datetime

class LocationManager:

    def __init__(self, history_size: int = 10):
        """
        Initialize the LocationManager.
        :param history_size: Only the last `history_size` days of location history will be kept.
        """

        self.history_size = history_size

        self.last_location : (float, float)  = None
        self.last_location_timestamp: datetime | None = None

        self.current_location : LocationRecord | None = None

        self.locations : list[StaticLocation] = []
        self.location_history : list[LocationRecord] = []


        self.speed: float = 0.0  # Speed in km/h

        self._load()

    def _save(self):

        self.location_history = [record for record in self.location_history if (datetime.now() - record.entered).days < self.history_size]

        ValkeyDB().set_serialized(DatabaseConstants.LOCATION, self.locations)
        ValkeyDB().set_serialized(DatabaseConstants.LOCATION_HISTORY, self.location_history)

    def _load(self):
        self.locations = ValkeyDB().get_serialized(DatabaseConstants.LOCATION, [])
        self.location_history = ValkeyDB().get_serialized(DatabaseConstants.LOCATION_HISTORY, [])


    def _find_location_by_coordinates(self, latitude: float, longitude: float) -> StaticLocation | None:
        """
        Find a location by its coordinates.
        Returns the StaticLocation if found, otherwise None.
        """

        locations = [location for location in self.locations if geodesic((latitude, longitude), (location.latitude, location.longitude)).meters <= location.radius]
        locations = sorted(locations, key=lambda loc: geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters)

        if locations:
            return locations[0]

        return None

    def record_live_location(self, latitude: float, longitude: float):
        """
        Record a live location with latitude, longitude and radius.
        """

        location = self._find_location_by_coordinates(latitude, longitude)

        ## First record can't tell us that much
        if not self.last_location:
            # If no last location, initialize it
            self.last_location = (latitude, longitude)
            self.last_location_timestamp = datetime.now()

            self.current_location = LocationRecord(
                location=location,
                exited=datetime.now(),
                entered=datetime.now()
            )

            return

        time_delta = datetime.now() - self.last_location_timestamp

        self.speed = geodesic((latitude, longitude), (self.last_location[0], self.last_location[1])).meters / time_delta.seconds
        ## To km/h
        self.speed *= 3.

        if location != self.current_location.location:

            self.current_location.exited = datetime.now()

            self.location_history.append(self.current_location)

            self.current_location = LocationRecord(
                location=location,
                exited=datetime.now(),
                entered=datetime.now()
            )


        self.last_location = (latitude, longitude)
        self.last_location_timestamp = datetime.now()
        self._save()


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
        Returns a StaticLocation object or None if no location is recorded.
        """
        return self.current_location




    def add_static_location(self, name: str, description: str, latitude: float, longitude: float, radius: float):
        """
        Add a static location to the manager.
        """
        new_location = StaticLocation(name=name, description=description, latitude=latitude, longitude=longitude, radius=radius)
        self.locations.append(new_location)
        self._save()

    def closest_location(self, latitude: float, longitude: float, k: int = 1) -> list[StaticLocation]:
        """
        Find the closest k locations to the given coordinates.
        Returns a list of StaticLocation objects.
        """
        if not self.locations:
            return []

        locations = sorted(
            self.locations,
            key=lambda loc: geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters
        )

        return locations[:k]

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
        self.locations = [loc for loc in self.locations if loc.name != name]
        self._save()

