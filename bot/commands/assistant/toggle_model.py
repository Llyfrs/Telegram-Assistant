from bot.classes.command import command
from openai_api import OpenAI_API

MODELS = ["gpt-4o", "gpt-4o-mini", "o4-mini"]

@command
async def toggle_model(update, context):
    client : OpenAI_API = context.bot_data["client"]

    for i, model in enumerate(MODELS):
        if model == client.model:
            client.set_model(MODELS[(i + 1) % len(MODELS)])
            break

    await update.message.reply_text(f"Model is now {client.model}")