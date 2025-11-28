from modules.Settings import Settings
import wolframalpha

from modules.database import MongoDB


def calculate(expression):
    """Calculates the given expression using WolframAlpha's API."""

    app_id = MongoDB().get("wolframalpha_app_id")

    if app_id is None:
        return "WolframAlpha app id not set"

    client = wolframalpha.Client(app_id)
    res = client.query(expression)
    answer = next(res.results).text
    return answer
