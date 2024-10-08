from datetime import datetime

from modules.database import ValkeyDB


class TimeTable:
    def __init__(self, timezone):
        self.db = ValkeyDB()
        self.timezone : datetime.tzinfo  = timezone
        self.timetable = self.db.get_serialized("timetable", {})


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
            start = datetime.strptime(lesson["start"], "%H:%M")
            end = datetime.strptime(lesson["end"], "%H:%M")

            if start <= now <= end:
                return lesson

        return self.next()

    def next(self):
        day = datetime.now(self.timezone).strftime("%A").lower()
        now = datetime.now(self.timezone)

        if day not in self.timetable:
            return None

        lessons = self.timetable[day].sort(key=lambda x: datetime.strptime(x["start"], "%H:%M"))

        for lesson in lessons:
            start = datetime.strptime(lesson["start"], "%H:%M")

            if start >= now:
                return lesson

        return None



    def clear(self, day):
        self.timetable[day] = []
        self.db.set_serialized("timetable", self.timetable)