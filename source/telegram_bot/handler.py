import html
import json
import os
import traceback
from datetime import datetime

from chat import ChatMessage
from constants import Role, system_prompts
from llm_models import ChatHistory, Model, OpenAIChatInterface

# from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils import logger

BOT_NAME = os.environ.get("BOT_NAME")


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
        ChatHistory.reset()
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
        def gpt_chat_response(text: str, chat) -> str:
            username = f"{chat.first_name} {chat.last_name}"

            user_msg = ChatMessage(
                role=Role.USER,
                username=username,
                content=text,
                timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            )
            ChatHistory.insert(user_msg)

            messages = ChatHistory.truncate_messages()
            response_msg = OpenAIChatInterface.chat_text(
                messages=messages,
            )
            assistant_msg = ChatMessage(
                role=Role.ASSISTANT,
                username="Assistant",
                content=response_msg,
                timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            )
            ChatHistory.insert(assistant_msg)

            return response_msg

        input_text = update.message.text
        logger.info(f"input text: {input_text}")

        image_prompt = OpenAIChatInterface.chat_text(
            messages=[
                {"role": Role.SYSTEM.value, "content": system_prompts.IMAGE_PROMPT},
                {"role": Role.USER.value, "content": input_text},
            ]
        )
        logger.info(f"image prompt: {image_prompt}")

        if "@image" in image_prompt:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=OpenAIChatInterface.chat_image(prompt=image_prompt),
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=gpt_chat_response(input_text, update.message.chat),
                parse_mode=ParseMode.MARKDOWN,
            )


class BotVisionCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # chooser the largest photo size
        input_photo = await context.bot.get_file(update.message.photo[-1].file_id)
        image_url = input_photo.file_path

        input_text = update.message.caption if update.message.caption else ""
        logger.info(f"input_photo: {image_url}")
        logger.info(f"input_text: {input_text}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=OpenAIChatInterface.chat_vision(
                caption=input_text,
                image_url=image_url,
            ),
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
