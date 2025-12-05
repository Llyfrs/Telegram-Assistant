import os

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from enums.bot_data import BotData
from utils.logging import get_logger

logger = get_logger(__name__)

AWAITING_MODEL = 0


async def start_model_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point - prompt user for model name."""
    current_agent: Agent = context.bot_data.get(BotData.MAIN_AGENT)
    current_model = getattr(current_agent.model, 'model_name', 'unknown') if current_agent else 'unknown'
    
    await update.message.reply_text(
        f"Current model: `{current_model}`\n\n"
        "Enter the OpenRouter model name to switch to "
        "(e.g. `deepseek/deepseek-chat`, `openai/gpt-4o-mini`):\n\n"
        "Use /cancel to abort.",
        parse_mode="Markdown"
    )
    return AWAITING_MODEL


async def handle_model_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and switch to the provided model."""
    model_name = update.message.text.strip()
    
    if not model_name:
        await update.message.reply_text(
            "Model name cannot be empty. Please try again or /cancel."
        )
        return AWAITING_MODEL
    
    # Try to create the model and make a simple test call
    try:
        provider = OpenRouterProvider(api_key=os.getenv("OPENROUTER_API_KEY"))
        new_model = OpenRouterModel(model_name, provider=provider)
        
        # Update the agent's model
        agent: Agent = context.bot_data[BotData.MAIN_AGENT]
        agent.model = new_model
        context.bot_data[BotData.MAIN_AGENT] = agent
        
        await update.message.reply_text(
            f"✓ Model switched to `{model_name}`",
            parse_mode="Markdown"
        )
        logger.info("Model switched to %s", model_name)
        return ConversationHandler.END
        
    except Exception as e:
        error_msg = str(e)
        logger.warning("Failed to switch model to %s: %s", model_name, error_msg)
        
        await update.message.reply_text(
            f"Failed to switch to `{model_name}`:\n"
            f"```\n{error_msg[:500]}\n```\n\n"
            "Please enter a valid OpenRouter model name or /cancel.",
            parse_mode="Markdown"
        )
        return AWAITING_MODEL


class ToggleModel(Command):
    priority = 1
    command_name = "model"
    
    @classmethod
    def handler(cls, app: Application) -> None:
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("model", start_model_switch)],
            states={
                AWAITING_MODEL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_model_input)
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        app.add_handler(conv_handler)
