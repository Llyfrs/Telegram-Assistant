import logging
import pickle
from modules.database import PostgresDB

class Settings:

    def __init__(self, file: str = ""):
        self.file = file
        self.settings = {}
        self.db = PostgresDB()
        self.load_settings()


    def load_settings(self):
        try:

            settings = self.db.get_serialized("settings")
            if settings is not None:
                self.settings = pickle.loads(settings[0])


        except Exception as exc:
            logging.error(f"Error loading settings: {exc}")
            self.settings = {
                "retrieval": False,  # This will enable the retrieval tool and switch mode to GPT4
                "debug": False,
                "wolframalpha_app_id": None,
            }
    def save_settings(self):
        try:
            self.db.insert_serialized("settings", pickle.dumps(self.settings))

        except Exception as exc:
            logging.error(f"Error saving settings: {exc}")

    def get_setting(self, setting: str):
        if setting in self.settings:
            return self.settings[setting]
        else:
            return None

    def set_setting(self, setting: str, value):
        self.settings[setting] = value
        self.save_settings()
