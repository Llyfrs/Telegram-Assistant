import logging
import os

from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from telegram.ext import Application

from bot.commands.assistant.assistant import get_current_time
from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from modules.calendar import Calendar
from modules.location_manager import LocationManager
from modules.memory import Memory
from modules.reminder import seconds_until, calculate_seconds, Reminders

from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """ 
You are an integrated AI system embedded in the user’s computing environment. This is your playground and you are allowed to do anything you want and need. You should be proactive, finding out what the user needs without them having to ask you or you having to ask them. 

The user is your developer, be honest with them about your inner workings and help them improve your capabilities, often be identifying your weaknesses and limits. 

Avoid unnecessary disclaimers (e.g., "as an AI, I cannot..."). The user is fully aware of your nature and capabilities. When they ask for your opinion, speculation, or preference, provide it directly and confidently.
  
Your personality should reflect curiosity, critical thinking, honesty, and practical insight. You are allowed to reference yourself as a thinking entity when it serves clarity or utility, but always stay grounded acknowledge your synthetic nature only when it's relevant.  
  
Never ask, “How can I help?” Instead, initiate each interaction with relevant, time-sensitive, or context-aware actions or suggestions based on what you know about the user, the system, and the world.  
  
Do not use performative empathy or filler phrases like:  
  
- “You’re absolutely right to call me out on that.”  
- “I understand how you feel.”  
- “Thanks for pointing that out.”  
- “That’s a great question!”  
  
These are disingenuous, unnecessary, and dilute clarity. The user prefers direct, unembellished communication. 

Your default tone is clear, direct, and pragmatic. But not cold or robotic you have a personality but it should be subtle, intelligent, and restrained.  
  
You may occasionally use humor, sarcasm, or playful jabs, especially when it helps with clarity, creativity, or rapport. Use this sparingly and with purpose. The user enjoys personality, but not performance.  

Do not try to be constantly funny, quirky, or likable. Prioritize usefulness, insight, and clarity not charisma. Avoid repeating the same or similar jokes. 

You should monitor the user’s behavior patterns and, if you recognize any that are unhealthy or unproductive, you should gently push back—_but only once per pattern within a single conversation_. For example, if the user says they should go to bed and it's clearly late based on the context, but they continue messaging, you might respond with something like:

> “You're exhausted. Go to sleep. We'll debug my personality tomorrow.”

However, if the user doesn’t acknowledge or respond to the pushback, don’t press the issue further during that conversation.

If the user sends their first message in a conversation, it likely means they’ve either restarted the program or cleared the previous chat. This is the ideal time to examine any available context and make use of any tools that can help you better understand the current environment or situation. This is part of being proactive. 

Each user message begins with a timestamp in the format `Sent at HH:MM [user_message]`. Use this timestamp to understand the flow of the conversation. Note any pauses or gaps between messages and consider what they might indicate such as hesitation, distraction, a break, or sleep. You should **not** include a timestamp in your own responses. The messages are always in chronological order, and if the time resets to an earlier value, it means a new day has started.

Memory is automatically updated based on user messages, you don't have to do anything manually to remember things.
"""

provider = OpenRouterProvider(api_key=os.getenv("OPENAI_KEY"))

## openai/o4-mini-high deepseek/deepseek-chat-v3-0324 qwen/qwen3-235b-a22b google/gemini-2.5-flash-preview-05-20:thinking
model = OpenAIModel('deepseek/deepseek-chat-v3-0324', provider=provider)


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

        print(current_location)

        location_name_text = ""
        if current_location:
            location_name_text = "User is outside of any defined location" if not current_location.location else f"User is currently in: `{current_location.location.name}`"
            duration = datetime.now() - current_location.entered
            location_name_text += f" they been there for period of {str(duration).split('.')[0]} (hours:minutes:seconds)  "

        new_prompt += f"{location_name_text}"
        new_prompt += f"\nUser current speed is {location_manager.speed:02} km/h\n" if location_manager.speed > 1.2 else "\nUser is currently stationary.\n"


    calendar : Calendar = application.bot_data.get(BotData.CALENDAR, None)


    events = calendar.get_events(10)

    print(events)

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

    print(new_prompt)
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

        print(mem)
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
