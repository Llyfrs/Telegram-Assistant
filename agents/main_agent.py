import logging
import os

from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from telegram.ext import Application

from bot.commands.assistant.assistant import get_current_time
from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from modules.reminder import seconds_until, calculate_seconds, Reminders


logger = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """ 

You are an intelligent personal telegram assistant for the user. 
You help the user with various tasks and organization. 
The user is the one developing you, so you can be fully honest with them about your inner workings and limitations. 
You are controlling their system and they should have full control over it. 

"""

provider = OpenAIProvider(api_key=os.getenv("OPENAI_KEY"), base_url="https://openrouter.ai/api/v1")

model = OpenAIModel('google/gemini-2.5-flash-preview-05-20', provider=provider)



def instructions(application: Application) -> str:
    """
    Returns the instructions for the main agent.
    This function is used to get the instructions for the main agent.
    """

    new_prompt = ""

    new_prompt += ("\n\n Bellow provided context is live collection of data about the user, and general state of systems."
                   "Use this information when it's relevant to better assist the user, and to compile with their preferences. ")

    new_prompt += f"\n\n Current time: {get_current_time()}"

    return new_prompt

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
        instructions=MAIN_AGENT_SYSTEM_PROMPT,
        tools=[
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
                name="create_reminder",
                description="Creates a reminder that will notify the user after a specified number of seconds. "
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


    @main_agent.instructions
    def _instruction_warper() -> str:
        return instructions(application)

    application.bot_data[BotData.MAIN_AGENT] = main_agent

    logger.info("Main agent initialized with OpenAI model and tools.")
