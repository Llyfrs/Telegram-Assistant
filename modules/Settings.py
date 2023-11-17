import pickle


class Settings:

    def __init__(self, file: str):
        self.file = file
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        try:
            with open(self.file, "rb") as file:
                self.settings = pickle.load(file)
        except Exception as exc:
            self.settings = {
                "retrieval": False,  # This will enable the retrieval tool and switch mode to GPT4
                "debug": False,
                "wolframalpha_app_id": None,
            }

    def save_settings(self):
        try:
            with open(self.file, "wb") as file:
                pickle.dump(self.settings, file)
        except Exception as exc:
            print(f"Error saving settings: {exc}")

    def get_setting(self, setting: str):
        if setting in self.settings:
            return self.settings[setting]
        else:
            return None

    def set_setting(self, setting: str, value):
        self.settings[setting] = value
        self.save_settings()
