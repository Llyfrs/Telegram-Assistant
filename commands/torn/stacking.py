from commands.command import command


@command
async def stacking(update, context):
    torn = context.bot_data["torn"]
    torn.set_stacking(not torn.get_stacking())
    await update.message.reply_text(f"Stacking is now: {torn.get_stacking()}")