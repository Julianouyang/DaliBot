import html
import json
import logging
import os
import traceback
import base64
from enum import Enum
from typing import List
from io import BytesIO

import tiktoken
# from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters, Updater)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("Dalibot")

HEROKU_DOMAIN = os.environ.get("HEROKU_DOMAIN")

class ROLE(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class DaliBotCore:
    SYSTEM_MSG = "You are a helpful assistant."
    # cache
    msg_cache = []
    # model
    CHAT_MODEL = "gpt-4-vision-preview"
    IMAGE_MODEL = "dall-e-3"

    client = OpenAI(api_key=os.environ.get("OPENAI_TOKEN"))

    def __init__(self) -> None:
        # Set up Telegram API keys
        self.telegram_bot_token = os.environ.get("TELEGRAM_TOKEN")

        self.application = ApplicationBuilder().token(self.telegram_bot_token).build()

    def run_local(self):
        logger.info("running local")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def run_webhook(self):
        logger.info("running webhook")
        self.application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', "8443")),
            url_path=self.telegram_bot_token,
            webhook_url=f"{HEROKU_DOMAIN}/{self.telegram_bot_token}",
        )

    def attach_handlers(self):
        start_handler = CommandHandler("start", DaliBotCore.start_func)
        reset_handler = CommandHandler("reset", DaliBotCore.reset_func)
        system_handler = CommandHandler("system", DaliBotCore.system_func)
        model_handler = CommandHandler("model", DaliBotCore.set_model)
        # add error handler
        gpt_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND), DaliBotCore.handle_message
        )
        vision_handler = MessageHandler(
            filters.PHOTO, DaliBotCore.handle_vision
        )

        # Add handlers
        self.application.add_handler(start_handler)
        self.application.add_handler(reset_handler)
        self.application.add_handler(system_handler)
        self.application.add_handler(model_handler)
        self.application.add_error_handler(DaliBotCore.error_handler)
        self.application.add_handler(gpt_handler)
        self.application.add_handler(vision_handler)

    @staticmethod
    async def start_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Welcome! I'm a ChatGPT-powered Pancakebot.",
        )

    @staticmethod
    async def reset_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
        DaliBotCore.msg_cache = []
        DaliBotCore.SYSTEM_MSG = "You are a helpful assistant."
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Reset..")

    @staticmethod
    async def system_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
        DaliBotCore.msg_cache = []
        DaliBotCore.SYSTEM_MSG = (" ").join(context.args)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sure.")

    @staticmethod
    async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
        model = (" ").join(context.args)
        if "4" in model:
            DaliBotCore.CHAT_MODEL = "gpt-4-turbo-preview"
        else:
            DaliBotCore.CHAT_MODEL = "gpt-3.5-turbo"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Changing model to {DaliBotCore.CHAT_MODEL}",
        )

    @staticmethod
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        # Log the error before we do anything else, so we can see it even if something breaks.
        logger.error("Exception while handling an update:", exc_info=context.error)

        # traceback.format_exception returns the usual python message about an exception, but as a
        # list of strings rather than a single string, so we have to join them together.
        tb_list = traceback.format_exception(
            None, context.error, context.error.__traceback__
        )
        tb_string = "".join(tb_list)

        # Build the message with some markup and additional information about what happened.
        # You might need to add some logic to deal with messages longer than the 4096 character limit.
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            "An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # Finally, send the message
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML
        )

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # load encoding for model
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(DaliBotCore.CHAT_MODEL)

        def gpt_chat_response(text: str) -> str:
            client: OpenAI = DaliBotCore.client
            system_messge = [
                {"role": ROLE.SYSTEM.value, "content": DaliBotCore.SYSTEM_MSG}
            ]
            cur_msg = [{"role": ROLE.USER.value, "content": text}]
            messages = truncate_messages(DaliBotCore.msg_cache)

            response = client.chat.completions.create(
                model=DaliBotCore.CHAT_MODEL,
                messages=system_messge + messages + cur_msg,
                temperature=1,
            )

            response_msg = response.choices[0].message.content.strip()
            logger.info(f"token used: {response.usage.total_tokens}")

            DaliBotCore.msg_cache.extend(
                [
                    {
                        "role": ROLE.SYSTEM.value,
                        "name": "example_assistant",
                        "content": response_msg,
                    },
                    {
                        "role": ROLE.SYSTEM.value,
                        "name": "example_user",
                        "content": text,
                    },
                ]
            )
            return response_msg

        def gpt_image_response(text: str) -> str:
            client: OpenAI = DaliBotCore.client
            response = client.images.generate(
                model=DaliBotCore.IMAGE_MODEL, prompt=text, n=1, size="1024x1024"
            )
            return response.data[0].url

        def truncate_messages(
            messages: List[dict], max_tokens: int = 2048, max_messages: int = 8
        ) -> List[dict]:
            total_tokens = 0
            total_messages = 0
            truncated_messages = []

            for message in reversed(messages):
                total_tokens += len(encoding.encode(json.dumps(message)))
                total_messages += 1
                if total_tokens <= max_tokens and total_messages < max_messages:
                    truncated_messages.insert(0, message)
                else:
                    break

            return truncated_messages

        input_text = update.message.text
        _image_prompt = f"""Use your best judgement to analyze this user prompt,
            and find out if user wants a text or image response.
            If the user wants to draw or return an image, generate an image prompt for it and append @image.
            This prompt will be sent to dall-e-3 model for image generation.
            For example, if user asks to create a dog image, you return '@image [your_detailed_image_prompt]`.
            If the user wants text response, just return '@noimage'.
        """
        check_for_image_response = DaliBotCore.client.chat.completions.create(
            model=DaliBotCore.CHAT_MODEL,
            messages=[
                {"role": ROLE.SYSTEM.value, "content": _image_prompt},
                {"role": ROLE.USER.value, "content": input_text},
            ],
            temperature=0.2,
        )

        image_result = check_for_image_response.choices[0].message.content.strip()
        print(image_result)
        if "@image" in image_result:
            response = {"type": "image", "content": gpt_image_response(image_result)}
        else:
            response = {"type": "text", "content": gpt_chat_response(input_text)}

        if response["type"] == "text":
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=response["content"]
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=response["content"]
            )

    @staticmethod
    async def handle_vision(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # chooser the largest photo size
        input_photo = await context.bot.get_file(update.message.photo[-1].file_id)
        photo_url = input_photo.file_path

        input_text = update.message.caption if update.message.caption else ""
        logger.info(f"input_photo: {photo_url}")  # Log the beginning of the base64 string
        logger.info(f"input_text: {input_text}")

        def gpt_vision_response(image, text: str="") -> str:
            client: OpenAI = DaliBotCore.client
            response = client.chat.completions.create(
                model=DaliBotCore.CHAT_MODEL, 
                messages=[
                    {"role": ROLE.USER.value, "content": [
                        {
                            "type": "text",
                            "text": text,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image
                            }
                        }
                    ]},
                ]
            )
            return response.choices[0]
        choice = gpt_vision_response(photo_url, input_text)
        response = {
            "type": "text", 
            "content": choice.message,
            "text": choice.message.content
        }
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=response["text"]
        )

def main():
    core = DaliBotCore()
    core.attach_handlers()
    logger.info("running core")
    core.run_webhook()
    logger.info("core up and running")


if __name__ == "__main__":
    main()
