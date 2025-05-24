import logging
import re
from datetime import datetime

import telegramify_markdown

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, \
    filters, Application

from bot.classes.command import Command
from modules.timetable import TimeTable

CHOOSE, DAY, COURSE, ROOM , TIME_START, TIME_END, CONFIRM = range(7)

LIST_DAYS, DELETE_COURSE = range(7, 9)

async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("Manage", callback_data="manage"),
         InlineKeyboardButton("Add Event", callback_data="add")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("What would you like to do time table?", reply_markup=reply_markup)

    return CHOOSE


async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(text="Selected option: {}".format(query.data))

    if query.data == "add":
        await update.effective_chat.send_message("Enter the day of the week")
        return DAY

    if query.data == "manage":
        timetable : TimeTable = context.bot_data["timetable"]

        keyboard = []

        for day in timetable.timetable:
            keyboard.append([InlineKeyboardButton(day.capitalize(), callback_data=day)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(telegramify_markdown.markdownify("*Days of the Week*"), reply_markup=reply_markup)

        return LIST_DAYS



async def list_days_to_message(query, context, day):
    timetable: TimeTable = context.bot_data["timetable"]

    keyboard = []

    lessons = timetable.get_day(day)

    for i, lesson in enumerate(lessons):
        keyboard.append([InlineKeyboardButton(f'{lesson["course"]} - {lesson["location"]} {lesson["start"]} - {lesson["end"]}', callback_data=f'{day} {i}')])

    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(telegramify_markdown.markdownify(f"*{day.capitalize()}*"), reply_markup=reply_markup, parse_mode="MarkdownV2")


async def list_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await list_days_to_message(query, context, query.data)

    return DELETE_COURSE


async def delete_course(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.delete_message()
        return ConversationHandler.END

    timetable: TimeTable = context.bot_data["timetable"]

    day, index = query.data.split(" ")

    timetable.remove(day, int(index))

    await list_days_to_message(query, context, day)

    return DELETE_COURSE


    pass

async def day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text

    logging.info(day)

    if day.lower() not in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        await update.message.reply_text("Invalid day, try again or /cancel")
        return DAY

    context.user_data["day"] = day.lower()

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
    start_time = update.message.text

    if not re.match(r"^\d{1,2}:\d{1,2}$", start_time):
        await update.message.reply_text("Invalid time format, try again or /cancel")
        return TIME_START

    context.user_data["time_start"] = start_time

    await update.message.reply_text("Enter the end time")
    return TIME_END

async def time_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time_end"] = update.message.text

    if not re.match(r"^\d{1,2}:\d{1,2}$", context.user_data["time_end"]):
        await update.message.reply_text("Invalid time format, try again or /cancel")
        return TIME_END

    if datetime.strptime(context.user_data["time_start"], "%H:%M") >= datetime.strptime(context.user_data["time_end"], "%H:%M"):
        await update.message.reply_text("End time is before start time, try again or /cancel")
        return TIME_END

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
        time_table = context.bot_data["timetable"]

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
            CHOOSE: [ CallbackQueryHandler(choose) ],
            DAY: [ MessageHandler(~filters.COMMAND, day) ],
            COURSE: [ MessageHandler(~filters.COMMAND, course) ],
            ROOM: [ MessageHandler(~filters.COMMAND, room) ],
            TIME_START: [ MessageHandler(~filters.COMMAND, time_start) ],
            TIME_END: [ MessageHandler(~filters.COMMAND, time_end) ],
            CONFIRM: [ CallbackQueryHandler(confirm) ],

            LIST_DAYS: [ CallbackQueryHandler(list_days) ],
            DELETE_COURSE: [ CallbackQueryHandler(delete_course) ]
        }, fallbacks=[ CommandHandler("cancel", cancel) ])


class TimeTable(Command):

    priority = 1

    @classmethod
    def handler(cls, app: Application):
        app.add_handler(time_table_handler())