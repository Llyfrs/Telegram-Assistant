from modules.Settings import Settings
import wolframalpha

from modules.database import ValkeyDB


def calculate(expression):
    """Calculates the given expression using WolframAlpha's API."""

    app_id = ValkeyDB().get_serialized("wolframalpha_app_id")

    if app_id is None:
        return "WolframAlpha app id not set"

    client = wolframalpha.Client(app_id)
    res = client.query(expression)
    answer = next(res.results).text
    return answer
