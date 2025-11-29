from telegram import Update, Location
from telegram.ext import Application, MessageHandler, filters, ContextTypes, ConversationHandler, CommandHandler

from bot.classes.command import Command
from bot.commands.time_table.time_table import cancel
from enums.bot_data import BotData
from modules.location_manager import LocationManager
from utils.logging import get_logger

logger = get_logger(__name__)

COLLECT_LOCATION_NAME, COLLECT_LOCATION_RADIUS, COLLECT_LOCATION_DESCRIPTION = range(3)


static_location_name = ""
static_location_radius = 0
static_location_description = ""
static_location_object : Location  | None = None


class LocationRecorder(Command):
    priority = 1
    register = False

    @classmethod
    def handler(cls, app):
        app.add_handler(
            ConversationHandler(
                entry_points=[MessageHandler(filters.LOCATION & ~filters.COMMAND, cls.handle)],
                states={
                    COLLECT_LOCATION_NAME:   [MessageHandler (~filters.COMMAND, cls.collect_location_name)],
                    COLLECT_LOCATION_RADIUS: [MessageHandler(~filters.COMMAND, cls.collect_location_radius)],
                    COLLECT_LOCATION_DESCRIPTION: [MessageHandler(~filters.COMMAND, cls.collect_location_description)],
                },
                fallbacks=[CommandHandler("cancel", cancel)]
            )
            , group=0)


    @classmethod
    async def handle(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle the location update
        global static_location_object

        location : LocationManager = context.bot_data[BotData.LOCATION]

        if update.edited_message:

            logger.debug("Live Location Update received")
            loc = update.edited_message.location
            location.record_live_location(loc.latitude, loc.longitude)

            pass

        if update.message and update.message.location.live_period is None:
            logger.debug("Manual location received")
            await update.message.reply_text(
                "Please provide a name for this location (e.g. 'Home', 'Work', etc.):"
            )
            static_location_object = update.message.location
            return COLLECT_LOCATION_NAME

        return -1

    @classmethod
    async def collect_location_name(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Collect the name for the location
        global static_location_name

        static_location_name = update.message.text.strip()

        await update.message.reply_text("Please provide radius in meters for this location:")
        return COLLECT_LOCATION_RADIUS

    @classmethod
    async def collect_location_radius(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Collect the radius for the location
        global static_location_radius

        radius = update.message.text

        if not radius.isdigit():
            await update.message.reply_text("Please provide a valid radius in meters.")
            return COLLECT_LOCATION_RADIUS

        static_location_radius = int(radius)

        await update.message.reply_text("Please provide a description for this location:")

        return COLLECT_LOCATION_DESCRIPTION

    @classmethod
    async def collect_location_description(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global static_location_description, static_location_object, static_location_name, static_location_radius

        location : LocationManager = context.bot_data[BotData.LOCATION]

        # Collect the description for the location
        static_location_description = update.message.text

        location.add_static_location(
            name=static_location_name,
            description=static_location_description,
            latitude=static_location_object.latitude,
            longitude=static_location_object.longitude,
            radius=static_location_radius
        )

        await update.message.reply_text(
            f"Location '{static_location_name}' with radius {static_location_radius} meters and description '{static_location_description}' has been added."
        )

        return ConversationHandler.END

