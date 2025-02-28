async def clear_thread(update, context):
    """ Clears the thread """

    client = context.bot_data["client"]
    client.clear_thread()
    await update.message.reply_text(f"Thread cleared")