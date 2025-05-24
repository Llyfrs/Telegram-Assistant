"""

Toggle for stacking mode in Torn. Changes some behaviour to take into account that the user is intentionally keeping energy above maximum.

"""

from bot.classes.command import command


@command
async def stacking(update, context):
    torn = context.bot_data["torn"]
    torn.set_stacking(not torn.get_stacking())
    await update.message.reply_text(f"Stacking is now: {torn.get_stacking()}")
