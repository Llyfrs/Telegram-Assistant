import logging
import os

from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from telegram.ext import Application

from bot.commands.assistant.assistant import get_current_time
from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from modules.reminder import seconds_until, calculate_seconds, Reminders

from openai.types.responses import FunctionTool

logger = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """ 
You are a personal telegram assistant for the user. 
You help the user with various tasks and organization. 
"""

provider = OpenAIProvider(api_key=os.getenv("OPENAI_KEY"))

settings = OpenAIResponsesModelSettings(
    openai_builtin_tools=[],
)

model = OpenAIResponsesModel('gpt-4o-mini', provider=provider)



def initialize_main_agent(application: Application):

    """
    Initializes the main agent with the OpenAI model and tools.
    This function should be called at the start of the application.
    """

    reminder =  Reminders(application.bot)
    application.bot_data[BotData.REMINDER] = reminder

    main_agent = Agent(
        name="Main Agent",
        model=model,
        system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
        model_settings=settings,
        tools=[
            Tool(
                name="get_current_time",
                description="Returns the current time in the format %H:%M:%S %d/%m/%Y",
                function=get_current_time
            ),
            Tool(
                name="seconds_until",
                description="Returns number seconds remaining to provided date. Date format has to be %Y-%m-%d %H:%M:%S. ",
                function=seconds_until
            ),
            Tool(
                name="convert_to_seconds",
                description="Converts days, hours, minutes and seconds to just seconds.",
                function=calculate_seconds
            ),
            Tool(
                name="add_reminder",
                description="Adds a reminder to the list of reminders. "
                            "This function is non blocking and will create a "
                            "new thread that notifies the user automatically.",
                function=reminder.add_reminder
            ),
            Tool(
                name="cancel_reminder",
                description="Cancels reminders specified by their IDs.",
                function=reminder.remove_reminders
            ),
            Tool(
                name="get_reminders",
                description="Returns list of all active reminders.",
                function=reminder.get_reminders
            ),
            Tool(
                name="create_event",
                description="Creates an event in a calendar. Use this for events that need continuous awareness, "
                            "unlike reminders that are set and forget.",
                function=blocking_add_event,
            ),
        ],
    )

    application.bot_data[BotData.MAIN_AGENT] = main_agent

    logger.info("Main agent initialized with OpenAI model and tools.")
