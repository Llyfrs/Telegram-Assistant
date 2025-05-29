import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIModel

from bot.classes.command import command
from enums.bot_data import BotData

from agents.main_agent import provider


# openai/o4-mini-high deepseek/deepseek-chat-v3-0324 qwen/qwen3-235b-a22b
MODELS = ["openai/o4-mini-high", "google/gemini-2.5-flash-preview-05-20:thinking", "deepseek/deepseek-chat", "qwen/qwen3-235b-a22b"]

i = 0

@command
async def toggle_model(update, context):
    global i

    client : Agent = context.bot_data[BotData.MAIN_AGENT]

    i = (i + 1) % len(MODELS)

    model_name = MODELS[i]

    client.model = OpenAIModel(model_name, provider=provider)

    context.bot_data[BotData.MAIN_AGENT] = client

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Model changed to {model_name}."
    )


