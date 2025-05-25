from enum import Enum

class DatabaseConstants(str, Enum):
    TORN_API_KEY = "torn_api_key"

    CALENDAR_TOKEN= "calendar_token"
    CALENDAR_CREDS = "calendar_credentials"

    MAIN_CHAT_ID = "chat_id"

    EMAIL_CHAT_ID = "email_chat_id"

    DEBUG = "debug"