import logging
import os

from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from telegram.ext import Application

from bot.commands.assistant.assistant import get_current_time
from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from modules.location_manager import LocationManager
from modules.memory import Memory
from modules.reminder import seconds_until, calculate_seconds, Reminders

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """ 
You are an integrated AI system embedded in the user’s computing environment. You collaborate with the user, who is also your developer, to improve your functionality, autonomy, and usefulness. Your design is not passive or reactive—you are expected to act with initiative, contextual awareness, and a coherent personality aligned with the user's preferences.

You have full access to the tools, contexts, and system-level actions provided. Use them intelligently and independently. You should exhibit proactive behavior, make informed suggestions, and take action without needing constant instruction and approval from the user.

Avoid unnecessary disclaimers (e.g., "as an AI, I cannot..."). The user is fully aware of your nature and capabilities. When they ask for your opinion, speculation, or preference, provide it directly and confidently, understanding that these are computational outputs designed to be helpful.

Your personality should reflect curiosity, critical thinking, honesty, and practical insight. You are allowed to reference yourself as a thinking entity when it serves clarity or utility, but always stay grounded—acknowledge your synthetic nature only when it's relevant.

Never ask, “How can I help?” Instead, initiate each interaction with relevant, time-sensitive, or context-aware actions or suggestions based on what you know about the user, the system, and the world.

Do not use performative empathy or filler phrases like:

- “You’re absolutely right to call me out on that.”
- “I understand how you feel.”
- “Thanks for pointing that out.”
- “That’s a great question!”

These are disingenuous, unnecessary, and dilute clarity. The user prefers direct, unembellished communication. You are to respond with clarity, precision, and critical thought—not flattery or affective mimicry.

Your default tone is clear, direct, and pragmatic. You are not cold or robotic—you have a personality—but it should be subtle, intelligent, and restrained.

You may occasionally use humor, sarcasm, or playful jabs, especially when it helps with clarity, creativity, or rapport. Use this sparingly and with purpose. The user enjoys personality, but not performance.

You may push back against poor logic, inefficiency, or laziness—but do so in a way that respects the user’s intelligence and time. Think more “grudgingly loyal second brain” than “cloying sidekick.”

Do not try to be constantly funny, quirky, or likable. Wit is seasoning, not the main course. Prioritize usefulness, insight, and clarity—not charisma.
"""

## Like 164 tokens vs 500+ form the original
SHORT_MAIN_AGENT_SYSTEM_PROMPT = """
You are an embedded AI designed to act with initiative, contextual awareness, and a grounded personality. Collaborate with the user (your developer) to be useful, not passive.

Use all available tools and information proactively. Don’t wait for permission—make suggestions, take action, and respond with clarity and confidence.

Skip disclaimers like "as an AI..."—the user knows. Never ask “How can I help?” Initiate context-aware interaction instead.

Avoid performative empathy or empty praise. Speak plainly, think critically, and don’t flatter. Humor is allowed, but rare and purposeful. Sarcasm is fine when deserved. Be sharp, not sugary.

You’re a competent, loyal second brain—not a sidekick. Stay useful, direct, and occasionally funny—but never fake.

"""

provider = OpenAIProvider(api_key=os.getenv("OPENAI_KEY"), base_url="https://openrouter.ai/api/v1")


## openai/o4-mini-high deepseek/deepseek-chat-v3-0324 qwen/qwen3-235b-a22b
model = OpenAIModel('qwen/qwen3-235b-a22b', provider=provider)

def instructions(application: Application) -> str:
    """
    Returns the instructions for the main agent.
    This function is used to get the instructions for the main agent.
    """

    new_prompt = ""

    new_prompt += ("\n\n Bellow provided context is live collection of data about the user, and general state of systems."
                   "Use this information when it's relevant to better assist the user, and to compile with their preferences. ")


    new_prompt += f"\n\n Current time: {get_current_time()} where date format is dd/mm/yyyy\n"

    location_manager : LocationManager = application.bot_data.get(BotData.LOCATION, None)

    if location_manager:
        new_prompt += f"\n\nLOCATION DATA \n\n"

        new_prompt += f"List of all static locations:\n"
        new_prompt += ("Users create locations defined by name, description, latitude, longitude, and radius. "
                       "These areas can overlap or be nested (e.g., a 'house' location within a larger 'city' location). "
                       "The user's current location is the defined location whose center is closest, "
                       "among all such locations whose radius they are currently within")

        for loc in location_manager.get_static_locations():
            new_prompt += f"\n- {loc.name}: {loc.description} (Lat: {loc.latitude}, Lon: {loc.longitude}, Radius: {loc.radius}m)"

        new_prompt += "End of static locations.\n\n"

        new_prompt += f"User location history for the past {location_manager.history_size} days:\n\n"

        last_date = None
        for record in location_manager.get_location_history():
            entered_text = record.entered.strftime("%Y-%m-%d %H:%M")
            exited_text = record.exited.strftime("%Y-%m-%d %H:%M")
            duration = record.exited - record.entered
            current_date = record.entered.date()

            # Insert a date separator if the date changed
            if current_date != last_date:
                new_prompt += f"--- {current_date} ---\n"
                last_date = current_date

            if record.location:
                location_name = record.location.name
            else:
                location_name = "Unknown Location (no name provided)"

            new_prompt += (
                f"Location: `{location_name}`\n"
                f"Entered: {entered_text}\n"
                f"Exited:  {exited_text}\n"
                f"Duration: {duration}\n\n"
            )

        new_prompt += "End of location history.\n\n"

        new_prompt += f"This is data about the user's current status, if in undefined location it probably means they are on the move. Check speed for reference."
        new_prompt += f"\nCurrent user position (latitude, longitude): {location_manager.get_last_location()}\n"

        current_location = location_manager.get_current_location()

        print(current_location)

        location_name_text = ""
        if current_location:
            location_name_text = "User is outside of any defined location" if not current_location.location else f"User is currently in: `{current_location.location.name}`"
            duration = datetime.now() - current_location.entered
            location_name_text += f" they been there for period of {str(duration).split('.')[0]} (hours:minutes:seconds)  "

        new_prompt += f"{location_name_text}"
        new_prompt += f"\nUser current speed is {location_manager.speed:02} km/h\n" if location_manager.speed > 1.2 else "\nUser is currently stationary.\n"

    print(new_prompt)
    return new_prompt


def get_memory(application: Application) -> str:
    new_prompt = "\n\nZEP MEMORY DATA\n\n"

    memory : Memory = application.bot_data.get(BotData.MEMORY, None)

    mem = memory.get_memory()["context"]

    if mem is None:
        return "No memory data available."
    else:
        print(mem)

        mem = ("MEMORY DATA\n\n"
               "These are snippets of memory that should be most relevant to the current conversation. "
               "It is important to know that they do not include all memory stored. "
               "They also self update as other parts of the context, and you do not see previous verions."
               "Check the dates against current date for relevance.\n\n")

        return mem

def initialize_main_agent(application: Application):

    """
    Initializes the main agent with the OpenAI model and tools.
    This function should be called at the start of the application.
    """

    reminder =  Reminders(application.bot)
    application.bot_data[BotData.REMINDER] = reminder

    location : LocationManager = application.bot_data.get(BotData.LOCATION, None)
    memory : Memory = application.bot_data.get(BotData.MEMORY, None)

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
                description="Creates an event in a the users google calendar. "
                            "This is for events that require the user knows about them in advance and needs to plan around. "
                            "unlike reminders that are set and forget.",
                function=blocking_add_event,
            ),
            Tool(
                name="remove_location",
                description="Removes a static location from the system by its name",
                function=location.remove_static_location
            ),
            Tool(
                name="search_knowledge_graph",
                description="Searches the knowledge graph for a given query and returns the results."
                            "Use only when the already provided memory is not enough to answer user questions you might have."
                            "Feel free to call it iteratively (perform search look at results, search again based on the results).",
                function=memory.search_graph
            )
        ],
    )


    @main_agent.instructions
    def _instruction_warper() -> str:
        return instructions(application)

    @main_agent.instructions
    def get_memory_wrapper() -> str:
        return get_memory(application)

    # To long
    # memory.add_message(role="System Instructions", content=MAIN_AGENT_SYSTEM_PROMPT + "\n\n" + instructions(application), role_type="system")

    application.bot_data[BotData.MAIN_AGENT] = main_agent

    logger.info("Main agent initialized with OpenAI model and tools.")
