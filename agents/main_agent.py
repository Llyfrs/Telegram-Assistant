import asyncio
import os
from pathlib import Path
from typing import Any, List, Optional

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from telegram.ext import Application, ContextTypes

from bot.watchers.email_summary import blocking_add_event
from enums.bot_data import BotData
from enums.database import DatabaseConstants
from modules.bot import Bot
from modules.database import MongoDB
from modules.file_system import DiskFileSystem
from modules.memory import Memory
from modules.reminder import Reminders, calculate_seconds, seconds_until
from utils.logging import get_logger

from modules.time_capsule import create_capsule as create_time_capsule
from modules.habits import (
    create_habit as create_habit_tool,
    get_active_habits as list_habits_tool,
    deactivate_habit as remove_habit_tool,
    get_habit_stats as get_habit_stats_tool,
)
from modules.habit_heatmap import generate_habit_heatmap as generate_heatmap_tool


logger = get_logger(__name__)

_MAIN_AGENT_PROMPT_PATH = Path(__file__).resolve().parent / "main_agent_prompt.md"


def load_main_agent_system_prompt() -> str:
    """Load the main agent system prompt from the markdown file next to this module."""
    return _MAIN_AGENT_PROMPT_PATH.read_text(encoding="utf-8")


MAX_AGENT_LOOPS = 10

_AGENT_CONTINUE_PROMPT = (
    "If this user message still needs another tool step, take it. "
    "If you are done for this message—whether that was casual chat, a simple answer, or multi-step work—"
    "use send_telegram_message when the user should see a reply, then call submit_solution with a short summary."
)


def submit_solution(summary: str = "") -> str:
    """
    Signals that this user message is fully handled for this run. Call once after any needed
    send_telegram_message (or when no reply is needed). Not limited to formal tasks—casual chat counts.
    """
    logger.debug("submit_solution summary: %s", summary)
    return "Turn complete. Episode ended."


provider = OpenRouterProvider(api_key=os.getenv("OPENROUTER_API_KEY"))
model = OpenRouterModel("z-ai/glm-5v-turbo", provider=provider)


class MainAgent:
    """
    Wraps the pydantic-ai Agent with internal message history and `call`, which runs up to
    MAX_AGENT_LOOPS turns until the model calls submit_solution or the cap is reached.
    """

    def __init__(self, application: Application) -> None:
        self._application = application
        self._message_history: List[Any] = []
        self._agent: Agent

        reminder = Reminders(application.bot)
        application.bot_data[BotData.REMINDER] = reminder

        memory: Memory = application.bot_data.get(BotData.MEMORY, None)
        file_manager: DiskFileSystem = application.bot_data.get(BotData.FILE_MANAGER, None)

        loop = asyncio.get_event_loop()

        def ensure_primary_bot() -> Optional[Bot]:
            bot_wrapper: Optional[Bot] = application.bot_data.get(BotData.BOT)

            if bot_wrapper:
                return bot_wrapper

            chat_id = MongoDB().get(DatabaseConstants.MAIN_CHAT_ID, None)

            if chat_id is None:
                return None

            if isinstance(chat_id, str):
                try:
                    chat_id = int(chat_id)
                except ValueError:
                    logger.error("Stored chat ID is not a valid integer: %s", chat_id)
                    return None

            bot_wrapper = Bot(application.bot, chat_id)
            application.bot_data[BotData.BOT] = bot_wrapper
            return bot_wrapper

        def send_telegram_message(text: str, markdown: bool = True, clean: bool = False) -> str:
            bot_wrapper = ensure_primary_bot()

            if bot_wrapper is None:
                warning = "Main chat ID is not configured; unable to deliver Telegram message."
                logger.warning(warning)
                return warning

            async def _send():
                await bot_wrapper.send(text, markdown=markdown, clean=clean)

            future = asyncio.run_coroutine_threadsafe(_send(), loop)

            try:
                future.result()
            except Exception as exc:  # pragma: no cover - safety net
                logger.error("Error while sending Telegram message: %s", exc)
                return f"Failed to send message: {exc}"

            if memory:
                try:
                    memory.add_message(role="Telegram Assistant", content=text, role_type="assistant")
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("Failed to persist assistant message to memory: %s", exc)

            return "Message sent to Telegram."

        def generate_heatmap(habit_id: str, period: str = "last_30_days") -> str:
            bot_wrapper = ensure_primary_bot()

            if bot_wrapper is None:
                warning = "Main chat ID is not configured; unable to deliver heatmap image."
                logger.warning(warning)
                return warning

            buf = generate_heatmap_tool(habit_id=habit_id, period=period)
            if buf is None:
                return "Failed to generate heatmap (habit not found or rendering error)."

            async def _send():
                await bot_wrapper.send_photo(
                    buf,
                    caption=f"Heatmap for `{habit_id}` ({period})",
                    markdown=True,
                    filename=f"habit_{habit_id}_{period}.png",
                )

            future = asyncio.run_coroutine_threadsafe(_send(), loop)
            try:
                future.result()
            except Exception as exc:  # pragma: no cover - safety net
                logger.error("Error while sending heatmap to Telegram: %s", exc)
                return f"Failed to send heatmap: {exc}"

            return "Heatmap sent to Telegram."

        self._agent = Agent(
            name="Main Agent",
            model=model,
            tools=[
                Tool(
                    strict=False,
                    name="seconds_until",
                    description="Returns number seconds remaining to provided date. Date format has to be %Y-%m-%d %H:%M:%S. ",
                    function=seconds_until,
                ),
                Tool(
                    strict=False,
                    name="convert_to_seconds",
                    description="Converts days, hours, minutes and seconds to just seconds.",
                    function=calculate_seconds,
                ),
                Tool(
                    strict=False,
                    name="create_reminder",
                    description="Creates a reminder that will notify the user after a specified number of seconds. "
                    "This function is non blocking and will create a "
                    "new thread that notifies the user automatically.",
                    function=reminder.add_reminder,
                ),
                Tool(
                    strict=False,
                    name="cancel_reminder",
                    description="Cancels reminders specified by their IDs.",
                    function=reminder.remove_reminders,
                ),
                Tool(
                    strict=False,
                    name="get_reminders",
                    description="Returns list of all active reminders.",
                    function=reminder.get_reminders,
                ),
                Tool(
                    strict=False,
                    name="create_event",
                    description="Creates an event in a the users google calendar. "
                    "This is for events that require the user knows about them in advance and needs to plan around. "
                    "unlike reminders that are set and forget.",
                    function=blocking_add_event,
                ),
                Tool(
                    strict=False,
                    name="send_telegram_message",
                    description="Sends a Markdown-formatted message to the user's primary Telegram chat. "
                    "Use this for any user-facing response.",
                    function=send_telegram_message,
                ),
                Tool(
                    strict=False,
                    name="submit_solution",
                    description="Call once when you are done with this user message for this run. "
                    "Not every message is a task—casual chat, questions, and small talk are normal; "
                    "still call this after you have replied (send_telegram_message when the user should see text) "
                    "or when no user-visible reply is needed. Pass a brief summary of what you did or said. "
                    "Calling this ends the multi-step loop for this message.",
                    function=submit_solution,
                ),
                Tool(
                    strict=False,
                    name="read_file",
                    description="Read a file's contents with line numbers. "
                    "Returns numbered lines (e.g. '  1|first line'). "
                    "Use offset (1-based line number) and limit (number of lines) for large files. "
                    "Always read a file before editing it with str_replace.",
                    function=file_manager.read_file,
                ),
                Tool(
                    strict=False,
                    name="write_file",
                    description="Create a new file or overwrite an existing file with the given content. "
                    "Parent directories are created automatically. "
                    "Use str_replace instead when making targeted edits to an existing file.",
                    function=file_manager.write_file,
                ),
                Tool(
                    strict=False,
                    name="str_replace",
                    description="Replace an exact string in a file. Provide old_str (the text to find) "
                    "and new_str (the replacement). old_str must match exactly one location in the file. "
                    "Include enough surrounding context (a few lines) in old_str to make it unique. "
                    "Whitespace and indentation must match exactly. "
                    "Always read_file first to see the current content before editing.",
                    function=file_manager.str_replace,
                ),
                Tool(
                    strict=False,
                    name="list_directory",
                    description="List files and directories at a path. "
                    "Shows directories with a trailing '/' and files with their size. "
                    "Omit path or pass empty string to list the root.",
                    function=file_manager.list_dir,
                ),
                Tool(
                    strict=False,
                    name="create_directory",
                    description="Create a directory and any missing parent directories.",
                    function=file_manager.mkdir,
                ),
                Tool(
                    strict=False,
                    name="delete",
                    description="Delete a file or directory. Directories are removed recursively.",
                    function=file_manager.delete,
                ),
                Tool(
                    strict=False,
                    name="move",
                    description="Move or rename a file or directory.",
                    function=file_manager.move,
                ),
                Tool(
                    strict=False,
                    name="search_files",
                    description="Search filenames and file contents for a query string. "
                    "Returns matching filenames and content lines with line numbers.",
                    function=file_manager.search,
                ),
                Tool(
                    strict=False,
                    name="create_time_capsule",
                    description="Creates a time capsule - a message to the user's future self. "
                    "Use this when the user wants to send a message, reminder, or note to themselves "
                    "at a future date (weeks, months, or even years ahead). "
                    "Unlike reminders which are task-oriented, time capsules are reflective messages "
                    "that will be delivered with distinctive formatting.",
                    function=create_time_capsule,
                ),
                Tool(
                    strict=False,
                    name="create_habit",
                    description="Creates a new habit to track daily. "
                    "habit_type: 'boolean' for yes/no habits, 'count' for quantity tracking. "
                    "options: for count type, list of button options (e.g., ['0', '1-2', '3-4', '5+']). "
                    "color: pick a color that matches the habit theme - "
                    "blue for calm/mindfulness, green for health/fitness, purple for creativity, "
                    "orange for productivity, red for intensity, cyan for hydration, pink for self-care. "
                    "Available colors: green, blue, purple, orange, red, cyan, pink.",
                    function=create_habit_tool,
                ),
                Tool(
                    strict=False,
                    name="list_habits",
                    description="Lists all active habits being tracked for the user.",
                    function=list_habits_tool,
                ),
                Tool(
                    strict=False,
                    name="remove_habit",
                    description="Deactivates a habit by its ID. The habit will no longer appear in daily check-ins.",
                    function=remove_habit_tool,
                ),
                Tool(
                    strict=False,
                    name="get_habit_stats",
                    description="Gets statistics for a habit. "
                    "For boolean habits: completion rate, current streak, best streak. "
                    "For count/numeric habits: average, trend (improving/declining), distribution, min/max values. "
                    "days: number of days to look back (default 30).",
                    function=get_habit_stats_tool,
                ),
                Tool(
                    strict=False,
                    name="generate_heatmap",
                    description="Generates a GitHub-style heatmap visualization for a habit and sends it as an image. "
                    "habit_id: the habit to visualize. "
                    "period: 'last_30_days', 'last_365_days', 'month:YYYY-MM', or 'year:YYYY'.",
                    function=generate_heatmap,
                ),
            ],
        )

        @self._agent.system_prompt
        def _system_prompt_warper() -> str:
            return load_main_agent_system_prompt()

    @property
    def model(self):
        return self._agent.model

    @model.setter
    def model(self, value) -> None:
        self._agent.model = value

    def clear_history(self) -> None:
        self._message_history = []

    async def _record_and_debug_response(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        response: Any,
        bot: Optional[Bot],
    ) -> dict[str, Any]:
        memory: Memory = context.bot_data.get(BotData.MEMORY, None)
        tool_calls: dict = {}
        bot_output = ""
        had_submit_solution = False

        for msg in response.new_messages():
            logger.debug("Message: %s", msg)
            parts = msg.parts
            for part in parts:
                if isinstance(part, ToolCallPart):
                    tool_calls[part.tool_call_id] = {
                        "name": part.tool_name,
                        "args": part.args,
                    }
                    if part.tool_name == "submit_solution":
                        had_submit_solution = True

                if isinstance(part, ToolReturnPart):
                    tool_calls[part.tool_call_id]["output"] = part.content

                if isinstance(part, TextPart):
                    bot_output += part.content + "\n"

        for _tool_call_id, tool_call in tool_calls.items():
            content = f"{tool_call['name']}({tool_call['args']}) => {tool_call.get('output', '')}"

            if len(content) > 2400:
                continue

            if memory:
                memory.add_message(
                    role=tool_call["name"],
                    content=f"{tool_call['name']}({tool_call['args']}) => {tool_call['output']}",
                    role_type="tool",
                )

        db = MongoDB()
        if db.get(DatabaseConstants.DEBUG, False) and bot is not None:
            for _tool_call_id, tool_call in tool_calls.items():
                await bot.send(f"`{tool_call['name']}({tool_call['args']}) => {tool_call['output']}`")

            await bot.send(f"Generated: `{bot_output}`")

        return {
            "tool_calls": tool_calls,
            "had_submit_solution": had_submit_solution,
        }

    async def call(self, context: ContextTypes.DEFAULT_TYPE, message_parts: list) -> None:
        bot: Optional[Bot] = context.bot_data.get(BotData.BOT)
        user_input: Any = message_parts
        any_send_telegram = False
        submitted = False

        for iteration in range(MAX_AGENT_LOOPS):
            response = await self._agent.run(user_input, message_history=self._message_history)
            self._message_history = response.all_messages()

            info = await self._record_and_debug_response(context, response, bot)
            tool_calls = info["tool_calls"]

            if any(call.get("name") == "send_telegram_message" for call in tool_calls.values()):
                any_send_telegram = True

            if info["had_submit_solution"]:
                submitted = True
                break

            if iteration < MAX_AGENT_LOOPS - 1:
                user_input = _AGENT_CONTINUE_PROMPT

        if not submitted:
            logger.warning(
                "Main agent reached max loops (%s) without submit_solution; "
                "send_telegram_message used in any iteration: %s",
                MAX_AGENT_LOOPS,
                any_send_telegram,
            )

        if not any_send_telegram:
            logger.warning("Direct Telegram request completed without calling send_telegram_message.")


def initialize_main_agent(application: Application) -> None:
    """
    Initializes the main agent with the OpenRouter model and tools.
    This function should be called at the start of the application.
    """
    application.bot_data[BotData.MAIN_AGENT] = MainAgent(application)
    logger.info("Main agent initialized.")
