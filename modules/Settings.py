from modules.database import MongoDB
from utils.logging import get_logger

logger = get_logger(__name__)


class Settings:

    def __init__(self, file: str = ""):
        self.file = file
        self.settings = {}
        self.db = MongoDB()
        self.load_settings()


    def load_settings(self):
        try:
            settings = self.db.get("settings")

        except Exception as exc:
            logger.error("Error loading settings: %s", exc)
            self.settings = {
                "retrieval": False,  # This will enable the retrieval tool and switch mode to GPT4
                "debug": False,
                "wolframalpha_app_id": None,
            }
    def save_settings(self):
        try:
            self.db.set("settings", self.settings)

        except Exception as exc:
            logger.error("Error saving settings: %s", exc)

    def get_setting(self, setting: str):
        if setting in self.settings:
            return self.settings[setting]
        else:
            return None

    def set_setting(self, setting: str, value):
        self.settings[setting] = value
        self.save_settings()
