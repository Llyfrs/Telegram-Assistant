import logging
from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Message
from telegram.ext import Application, ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes, \
    MessageHandler, filters

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from modules.database import MongoDB
from modules.torn import Torn


class CompanyState:
    COMPANY_MENU = 0
    TRAINING = 1
    COLLECT_PREFERENCE = 2
    LEAVE = -1


class Company(Command):


    main_message : Message = None
    cleanup : List[Message] = []

    @staticmethod
    def generate_menu_keyboard() -> InlineKeyboardMarkup:
        keyboard = [
            [ InlineKeyboardButton("Training Preferences", callback_data="training") ],
            [ InlineKeyboardButton("Cancel", callback_data="cancel") ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def generate_training_keyboard(context: ContextTypes.DEFAULT_TYPE):
        torn : Torn = context.bot_data["torn"]
        company_data = (await torn.get_company()).get("company_employees", {})

        keyboard = []

        employees_setting = MongoDB().get("company_employees", {})

        for employee in company_data:

            wage = company_data[employee].get("wage", 0)
            name = company_data[employee].get("name", "Unknown")

            if wage == 0:
                continue

            preference = employees_setting.get(employee, "None")

            keyboard.append([ InlineKeyboardButton( f'{name}: {preference}', callback_data=f"employee_{employee}") ])



        keyboard.append([ InlineKeyboardButton("Cancel", callback_data="cancel") ])

        return InlineKeyboardMarkup(keyboard)




    @classmethod
    async def start_company(cls, update : Update, context : ContextTypes.DEFAULT_TYPE):
        """Entry point for company command"""
        cls.main_message = await update.message.reply_text(
            "Click to toggle company settings:",
            reply_markup=cls.generate_menu_keyboard()
        )
        return CompanyState.COMPANY_MENU ## handle_menu_action()

    @classmethod
    async def handle_menu_action(cls, update, context):
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.delete_message()
            return ConversationHandler.END

        if query.data == "training":
            cls.main_message = await cls.main_message.edit_reply_markup(reply_markup=await cls.generate_training_keyboard(context))
            return CompanyState.TRAINING ## handle_training_action()


    @classmethod
    async def handle_training_action(cls, update: Update, context : ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.delete_message()
            return ConversationHandler.END

        employee_id = query.data.split("_")[1]

        mess = await update.effective_chat.send_message(f"Enter the preference for employee {employee_id}")

        cls.cleanup.append(mess)

        return CompanyState.COLLECT_PREFERENCE


    @classmethod
    async def collect_preference(cls, update, context: ContextTypes.DEFAULT_TYPE):
        preference = update.message.text

        cls.cleanup.append(update.message)

        ## Get the employee id
        employee_id = cls.cleanup[-2].text.split(" ")[-1]

        employees_setting = MongoDB().get("company_employees", {})

        employees_setting[employee_id] = preference

        MongoDB().set("company_employees", employees_setting)

        if cls.main_message.reply_markup != await cls.generate_training_keyboard(context):
            await cls.main_message.edit_reply_markup(reply_markup=await cls.generate_training_keyboard(context))

        for message in cls.cleanup:
            await message.delete()

        cls.cleanup = []

        return CompanyState.TRAINING




    @classmethod
    def handler(cls, app: Application) -> None:

        logging.info("Company command handler")

        app.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("company", cls.start_company)],
                states={
                    CompanyState.COMPANY_MENU: [
                        CallbackQueryHandler(cls.handle_menu_action),
                    ],
                    CompanyState.TRAINING: [
                        CallbackQueryHandler(cls.handle_training_action)
                    ],
                    CompanyState.COLLECT_PREFERENCE: [
                        MessageHandler(~filters.COMMAND, cls.collect_preference)
                    ]
                },
                fallbacks=[CommandHandler("cancel", cancel)],
                map_to_parent={ConversationHandler.END: -1}
            )
        )