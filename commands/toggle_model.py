from commands.command import command


@command
async def toggle_model(update, context):
    client = context.bot_data["client"]

    if client.model == "gpt-4o":
        client.set_model("gpt-4o-mini")
    else:
        client.set_model("gpt-4o")

    await update.message.reply_text(f"Model is now {client.model}")