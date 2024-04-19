import os

from llm_models import Model
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from utils import Singleton, logger

from .handler import (
    BotErrorCallback,
    BotMessageCallback,
    BotSystemModelCallback,
    BotSystemResetCallback,
    BotSystemStartCallback,
    BotVisionCallback,
)

HEROKU_DOMAIN = os.environ.get("HEROKU_DOMAIN")


class BotCore(metaclass=Singleton):
    def __init__(self) -> None:
        # Set up Telegram API keys
        self.telegram_bot_token = os.environ.get("TELEGRAM_TOKEN")
        self.application = ApplicationBuilder().token(self.telegram_bot_token).build()

        Model().set_current_chat_model(Model.CHAT_MODEL_VISION)
        Model().set_current_image_model(Model.IMAGE_MODEL)

    def run_local(self):
        logger.info("running local")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def run_webhook(self):
        logger.info("running webhook")
        self.application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", "8443")),
            url_path=self.telegram_bot_token,  # test leave it empty
            webhook_url=f"{HEROKU_DOMAIN}/{self.telegram_bot_token}",
        )

    def attach_handlers(self):
        start_handler = CommandHandler("start", BotSystemStartCallback.callback)
        reset_handler = CommandHandler("reset", BotSystemResetCallback.callback)
        model_handler = CommandHandler("model", BotSystemModelCallback.callback)
        gpt_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND), BotMessageCallback.callback
        )
        vision_handler = MessageHandler(filters.PHOTO, BotVisionCallback.callback)

        # Add handlers
        self.application.add_handler(start_handler)
        self.application.add_handler(reset_handler)
        self.application.add_handler(model_handler)
        self.application.add_handler(gpt_handler)
        self.application.add_handler(vision_handler)
        self.application.add_error_handler(BotErrorCallback.callback)
