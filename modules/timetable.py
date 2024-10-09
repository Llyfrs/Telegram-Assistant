import logging
from datetime import datetime

from modules.database import ValkeyDB


class TimeTable:
    def __init__(self, timezone):
        self.db = ValkeyDB()
        self.timezone : datetime.tzinfo  = timezone
        self.timetable = self.db.get_serialized("timetable", {})

        logging.info(f"TimeTable: {self.timetable}")


    def add(self, start, end, course, location, day):
        if day not in self.timetable:
            self.timetable[day] = []

        self.timetable[day].append({
            "start": start,
            "end": end,
            "course": course,
            "location": location
        })

        self.db.set_serialized("timetable", self.timetable)

    def now(self):
        day = datetime.now(self.timezone).strftime("%A").lower()
        now = datetime.now(self.timezone)

        if day not in self.timetable:
            return None

        for lesson in self.timetable[day]:
            # Combine the current date with the start and end times
            start = now.replace(hour=int(lesson["start"].split(":")[0]), minute=int(lesson["start"].split(":")[1]),
                                second=0, microsecond=0)
            end = now.replace(hour=int(lesson["end"].split(":")[0]), minute=int(lesson["end"].split(":")[1]), second=0,
                              microsecond=0)

            if start <= now <= end:
                return lesson

        return self.next()

    def next(self):
        day = datetime.now(self.timezone).strftime("%A").lower()
        now = datetime.now(self.timezone)

        if day not in self.timetable:
            return None

        lessons = sorted(self.timetable[day], key=lambda x: datetime.strptime(x["start"], "%H:%M"))

        for lesson in lessons:
            # Combine the current date with the start time
            start = now.replace(hour=int(lesson["start"].split(":")[0]), minute=int(lesson["start"].split(":")[1]),
                                second=0, microsecond=0)

            if start >= now:
                return lesson

        return None

    def remove(self, day, index):
        self.timetable[day].pop(index)

        if len(self.timetable[day]) == 0:
            self.timetable.pop(day)

        self.db.set_serialized("timetable", self.timetable)

    def clear(self, day):
        self.timetable[day] = []
        self.db.set_serialized("timetable", self.timetable)


    def get_day(self, day):
        return self.timetable.get(day, [])