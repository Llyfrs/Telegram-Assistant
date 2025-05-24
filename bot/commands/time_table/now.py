import telegramify_markdown
from bot.classes.command import command


@command
async def now(update, context):
    timetable = context.bot_data["timetable"]

    lesson = timetable.now()

    if lesson is None:
        await update.message.reply_text("No more lessons today")
        return

    reply = f"*{lesson['course']}*\n " \
            f"time: {lesson['start']}-{lesson['end']} \n" \
            f"location: {lesson['location']}"


    reply = telegramify_markdown.markdownify(reply)

    await update.message.reply_text(reply, parse_mode="MarkdownV2")

    pass