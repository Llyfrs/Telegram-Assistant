

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

    MEMORY = "memory"

    FILE_MANAGER = "file_manager"


    LOCATION = "location"

    EMAIL_CHAT_ID = "email_chat_id"

    MESSAGE_HISTORY = "message_history"
    BOT = "bot"