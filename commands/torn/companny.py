from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ConversationHandler, CommandHandler, CallbackQueryHandler, ContextTypes

from commands.command import command, Command
from modules.database import ValkeyDB
from modules.torn import Torn


class CompanyState:
    COMPANY_MENU = 0
    TRAINING = 1
    LEAVE = -1


class Company(Command):

    @staticmethod
    async def generate_menu_keyboard():
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

        employees_setting = ValkeyDB().get_serialized("company_employees", {})

        for employee in company_data:

            wage = company_data[employee].get("wage", 0)
            name = company_data[employee].get("name", "Unknown")

            if wage == 0:
                break

            preference = employees_setting.get(employee, "None")

            keyboard.append([ InlineKeyboardButton( f'{name}: {preference}', callback_data=f"employee_{employee}") ])


        keyboard.append([ InlineKeyboardButton("Cancel", callback_data="cancel") ])





    async def start_company(self, update, context):
        """Entry point for company command"""
        await update.message.reply_text(
            "Click to toggle company settings:",
            reply_markup=self.generate_menu_keyboard()
        )
        return CompanyState.MENU


    async def handle_menu_action(self, update, context):
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.delete_message()
            return ConversationHandler.END

        if query.data == "training":
            await query.message.edit_reply_markup(reply_markup=self.generate_training_keyboard(context))
            return CompanyState.TRAINING


    async def handle_training_action(self, update : Update, context : ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        employee_id = query.data.split("_")[1]

        await update.message.reply_text(f"Write a preference for {employee_id}")




    async def handler(cls, app: Application) -> None:
        app.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("company", cls.start_company)],
                states={
                    CompanyState.COMPANY_MENU: [
                        CallbackQueryHandler(cls.handle_menu_action),


                    ]
                },
                fallbacks=[CommandHandler("cancel", cancel)],
                map_to_parent={ConversationHandler.END: -1}
            )
        )