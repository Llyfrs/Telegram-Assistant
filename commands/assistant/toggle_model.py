from commands.command import command


MODELS = ["gpt-4o", "gpt-4o-mini", "o3-mini"]

@command
async def toggle_model(update, context):
    client = context.bot_data["client"]

    for i, model in enumerate(MODELS):
        if model == client.model:
            client.model = MODELS[(i + 1) % len(MODELS)]
            break

    await update.message.reply_text(f"Model is now {client.model}")