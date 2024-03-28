import base64
import html
import json
import logging
import os
import traceback
from enum import Enum
from io import BytesIO
from typing import List

# from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    Updater,
    filters,
)

from utils import logger
from llm_models import Model, ChatHistory
from constants import Role, system_prompts

BOT_NAME = os.environ.get("BOT_NAME")
client = OpenAI(api_key=os.environ.get("OPENAI_TOKEN"))


class Handler:
    @staticmethod
    async def callback(*args, **kwargs):
        raise NotImplementedError("This method should be overridden by subclasses.")


class BotSystemStartCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome! I'm a ChatGPT-powered {BOT_NAME}.",
        )


class BotSystemResetCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # DaliBotCore.msg_cache = []
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Reset..")


class BotSystemModelCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        model = (" ").join(context.args)
        if "4" in model:
            Model().set_current_chat_model("gpt-4-turbo-preview")
        elif "3" in model:
            Model().set_current_chat_model("gpt-3.5-turbo")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Changing model to {Model().get_current_chat_model()}",
        )


class BotMessageCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        def gpt_chat_response(text: str) -> str:
            system_messge = [
                {"role": Role.SYSTEM.value, "content": system_prompts.DEFAULT_PROMPT}
            ]
            cur_msg = [{"role": Role.USER.value, "content": text}]
            messages = ChatHistory.truncate_messages()

            response = client.chat.completions.create(
                model=Model().get_current_chat_model(),
                messages=system_messge + messages + cur_msg,
                temperature=1,
            )

            response_msg = response.choices[0].message.content.strip()
            logger.info(f"token used: {response.usage.total_tokens}")

            ChatHistory.insert(
                [
                    {
                        "role": Role.SYSTEM.value,
                        "name": "example_assistant",
                        "content": response_msg,
                    },
                    {
                        "role": Role.SYSTEM.value,
                        "name": "example_user",
                        "content": text,
                    },
                ]
            )
            return response_msg

        def gpt_image_response(text: str) -> str:
            response = client.images.generate(
                model=Model().get_current_image_model(),
                prompt=text,
                n=1,
                size="1024x1024",
            )
            return response.data[0].url

        input_text = update.message.text
        logger.info(f"input text: {input_text}")

        check_for_image_response = client.chat.completions.create(
            model=Model().get_current_chat_model(),
            messages=[
                {"role": Role.SYSTEM.value, "content": system_prompts.IMAGE_PROMPT},
                {"role": Role.USER.value, "content": input_text},
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
                chat_id=update.effective_chat.id,
                text=response["content"],
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=response["content"]
            )


class BotVisionCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # chooser the largest photo size
        input_photo = await context.bot.get_file(update.message.photo[-1].file_id)
        photo_url = input_photo.file_path

        input_text = update.message.caption if update.message.caption else ""
        logger.info(f"input_photo: {photo_url}")
        logger.info(f"input_text: {input_text}")

        def gpt_vision_response(image, text: str = "") -> str:
            response = client.chat.completions.create(
                model=Model().get_current_chat_model(),
                messages=[
                    {
                        "role": Role.USER.value,
                        "content": [
                            {
                                "type": "text",
                                "text": text,
                            },
                            {"type": "image_url", "image_url": {"url": image}},
                        ],
                    },
                ],
            )
            return response.choices[0]

        choice = gpt_vision_response(photo_url, input_text)
        response = {
            "type": "text",
            "content": choice.message,
            "text": choice.message.content,
        }
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response["text"],
            parse_mode=ParseMode.MARKDOWN,
        )


class BotErrorCallback(Handler):
    @staticmethod
    async def callback(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
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
