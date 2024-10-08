import logging

import pytz

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler

from modules.timetable import TimeTable

DAY, COURSE, ROOM , TIME_START, TIME_END, CONFIRM = range(6)

async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter the day of the week")
    return DAY


async def day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["day"] = update.message.text
    await update.message.reply_text("Enter the course")
    return COURSE

async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["course"] = update.message.text
    await update.message.reply_text("Enter the room")
    return ROOM

async def room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["room"] = update.message.text
    await update.message.reply_text("Enter the start time")
    return TIME_START


async def time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time_start"] = update.message.text
    await update.message.reply_text("Enter the end time")
    return TIME_END

async def time_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time_end"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="yes"), InlineKeyboardButton("No", callback_data="no")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"You have enetered the following data: \n"
                              f"Day: {context.user_data['day']} \n"
                              f"Course: {context.user_data['course']} \n"
                              f"Room: {context.user_data['room']} \n"
                              f"Start time: {context.user_data['time_start']} \n"
                              f"End time: {context.user_data['time_end']} \n"
                              f"Do you want to save this in to the time table?"
                                , reply_markup=reply_markup)

    return CONFIRM



async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):

    logging.info("Confirm")

    query = update.callback_query
    await query.answer()

    if  query.data == "yes":
        timezone = pytz.timezone('CET')
        time_table = TimeTable(timezone)

        # Save
        time_table.add(context.user_data["time_start"], context.user_data["time_end"], context.user_data["course"], context.user_data["room"], context.user_data["day"])

        await update.effective_chat.send_message("Data saved")


    else: # Cancel
        await update.effective_chat.send_message("Operation cancelled")

    await query.delete_message()

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled")
    return ConversationHandler.END

def time_table_handler():
    return ConversationHandler(
        entry_points=[ CommandHandler("time_table", enter) ],
        states={
            DAY: [ MessageHandler(None, day) ],
            COURSE: [ MessageHandler(None, course) ],
            ROOM: [ MessageHandler(None, room) ],
            TIME_START: [ MessageHandler(None, time_start) ],
            TIME_END: [ MessageHandler(None, time_end) ],
            CONFIRM: [ CallbackQueryHandler(confirm) ]
        }, fallbacks=[ CommandHandler("cancel", cancel) ])
