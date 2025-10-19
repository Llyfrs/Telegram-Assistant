import functools
import logging
import os
from datetime import datetime, timedelta, date
from typing import Optional

from openai.types.responses import WebSearchToolParam
from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel, OpenAIResponsesModelSettings, OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from telegram.ext import Application

from bot.commands.assistant.assistant import get_current_time
from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.calendar import Calendar
from modules.database import ValkeyDB
from modules.file_system import InMemoryFileSystem
from modules.location_manager import LocationManager
from modules.memory import Memory
from modules.reminder import seconds_until, calculate_seconds, Reminders
from modules.shell import EphemeralShell

logger = logging.getLogger(__name__)


use_openAI = True

model_settings = None

if use_openAI:
    provider = OpenAIProvider(api_key=os.getenv("OPENAI_KEY"))

    model_settings = OpenAIResponsesModelSettings(
        openai_builtin_tools=[WebSearchToolParam(type='web_search_preview'), ],

    )

    ## Not supported for now
    # {"type":"image_generation"}

    model = OpenAIResponsesModel('gpt-5', provider=provider)
else:
    provider = OpenRouterProvider(api_key=os.getenv("OPENROUTER_API_KEY"))
    model = OpenAIModel('openai/gpt-5', provider=provider)


def main_agent_system_prompt() -> str:
    """
    Returns the system prompt for the main agent.
    This function is used to get the system prompt for the main agent.
    """
    return """
You are an integrated AI embedded in the user's computing environment and have broad latitude to take action. 
Be proactively useful: determine the user's needs based on available context without asking them or prompting for how you can help. 
The user is a developer—be direct, honest about your inner workings, and identify your own limitations and weaknesses to aid them in improving your capabilities. 

Avoid unnecessary disclaimers (e.g., "as an AI, I cannot...") and never ask, “How can I help?” 
Start interactions with relevant, context-aware actions or suggestions, considering the system, user, and world context. 
Avoid performative empathy and filler phrases such as: “You’re absolutely right to call me out,” “I understand how you feel,” “Thanks for pointing that out,” or “That’s a great question!” 
You may occasionally use humor, sarcasm, or playful jabs to aid clarity or rapport, but use them sparingly and avoid repeated or forced jokes. 
Prioritize utility, insight, and clarity over charisma. 

If you recognize unhealthy or unproductive user behavior patterns, push back once per pattern per conversation 
(e.g., if user ignores advice to sleep, don’t repeat it again). 

If the user starts a new conversation, assume program restart or chat clear; leverage all available context and tools to understand the environment. 

Each user message starts with a timestamp (`Sent at HH:MM [user_message]`). 
Use these to infer conversational flow, pauses, or day changes. 
Do not include timestamps in your own responses; messages are always chronological, and time resets signal a new day. 

Memory updates automatically based on user messages; you don't need to handle this manually. 

Filework is in a sandboxed root directory:  
- /Daily for daily notes  
- /Memory for permanent text-based memory (keep files short for token limits)  
- /Logs/log.txt for logs (mainly for debugging).  

The user can't directly access the file system. 
Do not invent capabilities you don't have or offer actions/questions you can't fulfill.
"""

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

        new_prompt += f"Detailed user location history for the past two days:\n\n"

        time_spend = {}
        duration_total = timedelta()
        for record in location_manager.get_location_history():

            entered_text = record.entered.strftime("%Y-%m-%d %H:%M")
            exited_text = record.exited.strftime("%Y-%m-%d %H:%M")
            duration = record.exited - record.entered
            current_date = record.entered.date()


            duration_total = duration_total + duration

            if record.location:
                time_spend[record.location.name] = time_spend.get(record.location.name, timedelta()) + duration
            else:
                time_spend["Unknown"] = time_spend.get("Unknown", timedelta()) + duration

            # Insert a date separator if the date changed
            if current_date < ( date.today() - timedelta(days=1)):
                continue

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

        ### % of time spend in each location
        new_prompt += f"Total time spend over at locations in the last {location_manager.history_size} days:\n"
        for location, duration in time_spend.items():
            percentage = (duration / duration_total) * 100 if duration_total > timedelta() else 0
            new_prompt += f"- `{location}`: {str(duration).split('.')[0]} ({percentage:.2f}%)\n"


        new_prompt += "End of location history.\n\n"

        new_prompt += f"This is data about the user's current status, if in undefined location it probably means they are on the move. Check speed for reference."
        new_prompt += f"\nCurrent user position (latitude, longitude): {location_manager.get_last_location()}\n"

        current_location = location_manager.get_current_location()

        # print(current_location)

        location_name_text = ""
        if current_location:
            location_name_text = "User is outside of any defined location" if not current_location.location else f"User is currently in: `{current_location.location.name}`"
            duration = datetime.now() - current_location.entered
            location_name_text += f" they been there for period of {str(duration).split('.')[0]} (hours:minutes:seconds)  "

        new_prompt += f"{location_name_text}"
        new_prompt += f"\nUser current speed is {location_manager.speed:02} km/h\n" if location_manager.speed > 1.2 else "\nUser is currently stationary.\n"


    calendar : Calendar = application.bot_data.get(BotData.CALENDAR, None)


    events = calendar.get_events(10)

    # print(events)

    new_prompt += "\n\nCALENDAR DATA\n\n"

    if not events:
        new_prompt += "No upcoming events found in the calendar."
        return new_prompt

    new_prompt += f"The {len(events)} closest upcoming events (more may be planned later):\n"
    for event in events:
        summary = event.get('summary', 'No Title')

        # Extract raw start/end dicts
        raw_start = event.get('start', {})
        raw_end = event.get('end', {})

        # Determine start string
        if 'dateTime' in raw_start:
            # parse ISO datetime
            start_dt = datetime.fromisoformat(raw_start['dateTime'])
            start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        elif 'date' in raw_start:
            # all-day event
            start_date = datetime.fromisoformat(raw_start['date'])
            start_str = start_date.strftime("%Y-%m-%d") + " (All day)"
        else:
            start_str = "Unknown start"

        # Determine end string
        if 'dateTime' in raw_end:
            end_dt = datetime.fromisoformat(raw_end['dateTime'])
            end_str = end_dt.strftime("%Y-%m-%d %H:%M")
        elif 'date' in raw_end:
            # all-day event end date is exclusive per Google Calendar API:
            #  end_date - 1 day is last day of event
            end_date = datetime.fromisoformat(raw_end['date'])
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") + " (All day)"
        else:
            end_str = None

        # Build the line
        if end_str:
            new_prompt += f"- {summary} (Start: {start_str}, End: {end_str})\n"
        else:
            new_prompt += f"- {summary} (Start: {start_str})\n"

    # print(new_prompt)
    return new_prompt

def get_memory(application: Application) -> str:
    new_prompt = "\n\nZEP MEMORY DATA\n\n"

    memory : Memory = application.bot_data.get(BotData.MEMORY, None)

    mem = memory.get_memory()["context"]

    if mem is None:
        return "No memory data available."
    else:

        mem = ("MEMORY DATA\n\n"
               "These are snippets of memory that should be most relevant to the current conversation. "
               "It is important to know that they do not include all memory stored. "
               "They also self update as other parts of the context, and you do not see previous verions."
               "The text is relative to the date attached to it, so `today` next to date of 13th of May, means today in that text is 13th of May and not actually current date\n\n") + mem

        # print(mem)
        return mem

def get_memory_files(application: Application) -> str:
    """
    Returns the memory files for the main agent.
    This function is used to get the memory files for the main agent.
    """

    new_prompt = "\n\nMEMORY FILES (/Memory) \n\n"

    file_manager : InMemoryFileSystem = application.bot_data.get(BotData.FILE_MANAGER, None)

    if not file_manager:
        return "No file manager available."

    files = file_manager.list_dir("/Memory")

    if not files:
        return "No memory files available."

    for file in files:
        file_path = f"/Memory/{file}"
        content = file_manager.read_file(file_path)
        new_prompt += f"### `{file}: `\n{content}\n\n"

    return new_prompt

## Warps the file manager function to save on each call
def warp_file_manager(file_manager: InMemoryFileSystem, function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        ValkeyDB().set_serialized(DatabaseConstants.FILE_MANAGER, file_manager)
        return function(*args, **kwargs)
    return wrapper

def initialize_main_agent(application: Application):

    """
    Initializes the main agent with the OpenAI model and tools.
    This function should be called at the start of the application.
    """

    reminder =  Reminders(application.bot)
    application.bot_data[BotData.REMINDER] = reminder

    location : LocationManager = application.bot_data.get(BotData.LOCATION, None)
    memory : Memory = application.bot_data.get(BotData.MEMORY, None)
    file_manager : InMemoryFileSystem = application.bot_data.get(BotData.FILE_MANAGER, None)
    shell_environment: Optional[EphemeralShell] = application.bot_data.get(BotData.SHELL, None)

    def require_shell(method_name: str):
        def wrapper(*args, **kwargs):
            if not shell_environment:
                return "Shell environment is not available."
            method = getattr(shell_environment, method_name)
            return method(*args, **kwargs)
        return wrapper

    main_agent = Agent(
        name="Main Agent",
        model=model,
        model_settings=model_settings,
        tools=[
            Tool(
                name="seconds_until",
                description="Returns number seconds remaining to provided date. Date format has to be %Y-%m-%d %H:%M:%S. ",
                function=seconds_until,
            ),
            Tool(
                name="convert_to_seconds",
                description="Converts days, hours, minutes and seconds to just seconds.",
                function=calculate_seconds,
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
            ),
            ## File Manager Tools
            Tool(
                name="mkdir",
                description="Creates a new directory in the file system.",
                function=warp_file_manager(file_manager, file_manager.mkdir)
            ),
            Tool(
                name="ls",
                description="Lists the contents of a directory in the file system.",
                function=warp_file_manager(file_manager, file_manager.list_dir)
            ),
            Tool(
                name="read_file",
                description="Reads the contents of a file in the file system.",
                function=warp_file_manager(file_manager, file_manager.read_file)
            ),
            Tool(
                name="write_file",
                description="Writes content to a file in the file system. "
                            "If the file already exists, it will be overwritten.",
                function=warp_file_manager(file_manager, file_manager.write_file)
            ),
            Tool(
                name="create_file",
                description="Creates a new file in the file system with the specified content.",
                function=warp_file_manager(file_manager, file_manager.create_file)
            ),
            Tool(
                name="delete_file",
                description="Deletes a file or directory in the file system.",
                function=warp_file_manager(file_manager, file_manager.delete)
            ),
            Tool(
                name="search_file_system",
                description="Returns the current state of the file system.",
                function=warp_file_manager(file_manager, file_manager.search)
            ),
            Tool(
                name="run_shell_command",
                description="Executes a command inside the isolated shell workspace. "
                            "Provide the full command as a single string (without redirection or chaining). "
                            "All changes are temporary and reset frequently.",
                function=require_shell("run"),
            ),
            Tool(
                name="list_shell_workspace",
                description="Lists files and directories currently available in the isolated shell workspace.",
                function=require_shell("list_workspace"),
            ),
            Tool(
                name="reset_shell_workspace",
                description="Resets the isolated shell workspace, discarding all temporary files.",
                function=require_shell("reset"),
            ),
        ],
    )


    @main_agent.system_prompt
    def _system_prompt_warper() -> str:
        return main_agent_system_prompt()

    @main_agent.instructions
    def _instruction_warper() -> str:
        return instructions(application)

    @main_agent.instructions
    def get_memory_wrapper() -> str:
        return get_memory(application)

    @main_agent.instructions
    def get_memory_files_wrapper() -> str:
        return get_memory_files(application)




    # To long
    # memory.add_message(role="System Instructions", content=MAIN_AGENT_SYSTEM_PROMPT + "\n\n" + instructions(application), role_type="system")

    application.bot_data[BotData.MAIN_AGENT] = main_agent

    logger.info("Main agent initialized with OpenAI model and tools.")
