import html
import json
import os
import traceback

from chat import ChatMessage
from constants import Role, ChatType, system_prompts
from llm_models import ChatHistory, Model, OpenAIChatInterface
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils import logger

BOT_NAME = os.environ.get("BOT_NAME")

chatHistory = ChatHistory.getInstance()


class Handler:
    @staticmethod
    async def callback(*args, **kwargs):
        raise NotImplementedError("This method should be overridden by subclasses.")


class BotSystemStartCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome! I'm a GPT-powered {BOT_NAME}.",
        )


class BotSystemResetCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        ChatHistory.getInstance().reset()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Reset..")


class BotSystemModelCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        model = (" ").join(context.args)
        if "4" in model:
            Model().set_current_chat_model("gpt-4-turbo")
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
            )
            chatHistory.insert(user_msg)

            messages = chatHistory.truncate_messages()
            response_msg = OpenAIChatInterface.chat_text(
                messages=messages,
            )
            assistant_msg = ChatMessage(
                role=Role.ASSISTANT,
                username="Assistant",
                content=response_msg,
            )
            chatHistory.insert(assistant_msg)
            # push msgs to s3
            chatHistory.push_msgs_to_s3([user_msg, assistant_msg])
            return response_msg

        input_text = update.message.text
        logger.info(f"input text: {input_text}")
        # TODO use this to check if calling reasoning model
        image_prompt = OpenAIChatInterface.chat_text(
            model=Model.SIMPLE_CHAT_MODEL,
            messages=[
                {"role": Role.SYSTEM.value, "content": system_prompts.IMAGE_PROMPT},
                {
                    "role": Role.USER.value,
                    # make sure it's sending less than text limit
                    "content": input_text[:2048],
                },
            ],
            max_completion_tokens=512,
        )
        logger.info(f"image prompt: {image_prompt}")

        if "@image" in image_prompt:
            image_url = OpenAIChatInterface.chat_image(prompt=image_prompt)
            assistant_msg = ChatMessage(
                role=Role.ASSISTANT,
                username="Assistant-dalle",
                type=ChatType.IMAGE,
                content=input_text,
                image_url=image_url,
            )
            chatHistory.insert(assistant_msg)
            chatHistory.push_msgs_to_s3([assistant_msg])
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_url,
            )
        else:
            gpt_response = gpt_chat_response(input_text, update.message.chat)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=gpt_response,
                parse_mode=ParseMode.MARKDOWN,
            )


class BotVisionCallback(Handler):
    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.message.chat
        username = f"{chat.first_name} {chat.last_name}"
        # chooser the largest photo size
        input_photo = await context.bot.get_file(update.message.photo[-1].file_id)
        image_url = input_photo.file_path

        input_text = update.message.caption if update.message.caption else ""
        logger.info(f"input_photo: {image_url}")
        logger.info(f"input_text: {input_text}")
        user_msg = ChatMessage(
            role=Role.USER,
            username=username,
            content=input_text,
            type=ChatType.IMAGE,
            image_url=image_url,
        )
        chatHistory.insert(user_msg)
        out_text = OpenAIChatInterface.chat_vision(
            caption=input_text,
            image_url=image_url,
        )
        assistant_msg = ChatMessage(
            role=Role.ASSISTANT,
            username="Assistant",
            type=ChatType.TEXT,
            content=out_text,
        )
        chatHistory.insert(assistant_msg)
        chatHistory.push_msgs_to_s3([user_msg, assistant_msg])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=out_text,
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
