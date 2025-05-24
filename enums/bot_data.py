

from enum import Enum

class BotData(Enum):
    """
    Enum for bot data keys.
    """
    SETTINGS = "settings"
    CALENDAR = "calendar"
    TORN = "torn"
    REMINDER = "reminder"
    TIMETABLE = "timetable"
    MAIN_AGENT = "client"

    BOT = "bot"