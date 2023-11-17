from modules.Settings import Settings
import wolframalpha

settings = Settings("settings.pickle")


def calculate(expression):
    """Calculates the given expression using WolframAlpha's API."""
    global settings
    app_id = settings.get_setting("wolframalpha_app_id")

    if app_id is None:
        settings = Settings("settings.pickle")

    app_id = settings.get_setting("wolframalpha_app_id")

    if app_id is None:
        return "WolframAlpha app id not set"

    client = wolframalpha.Client(app_id)
    res = client.query(expression)
    answer = next(res.results).text
    return answer
