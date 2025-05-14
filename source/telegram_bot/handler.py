import html
import json
import os
import traceback
import base64
from io import BytesIO

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

        image_prompt = OpenAIChatInterface.chat_text(
            messages=[
                {"role": Role.SYSTEM.value, "content": system_prompts.IMAGE_PROMPT},
                {
                    "role": Role.USER.value,
                    # make sure it's sending less than text limit
                    "content": input_text[:2048],
                },
            ]
        )
        logger.info(f"image prompt: {image_prompt}")

        if "@image" in image_prompt:
            # Set response_format to b64_json to get base64 encoded image
            image_b64 = OpenAIChatInterface.chat_image(
                prompt=image_prompt,
            )
            # Store image data in chat history
            assistant_msg = ChatMessage(
                role=Role.ASSISTANT,
                username="Assistant",
                type=ChatType.IMAGE,
                content=input_text,
                image_b64=image_b64,
            )
            chatHistory.insert(assistant_msg)
            chatHistory.push_msgs_to_s3([assistant_msg])
            
            # Decode base64 string to binary
            image_data = base64.b64decode(image_b64)
            # Create an in-memory file-like object
            bio = BytesIO(image_data)
            bio.name = "image.png"  # Name is required for Telegram API
            
            # Send the image
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=bio,
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

        input_text = update.message.caption if update.message.caption else None
        logger.info(f"input_photo: {image_url}")
        logger.info(f"input_text: {input_text}")
        
        # Create user message with the image
        user_msg = ChatMessage(
            role=Role.USER,
            username=username,
            content=input_text if input_text else "",
            type=ChatType.IMAGE,
            image_url=image_url,
        )
        chatHistory.insert(user_msg)

        is_edit_request = False
        
        # Check if this is an edit request
        if input_text is not None:
            image_prompt = OpenAIChatInterface.chat_text(
                messages=[
                    {"role": Role.SYSTEM.value, "content": system_prompts.IMAGE_PROMPT},
                    {
                        "role": Role.USER.value,
                        # make sure it's sending less than text limit
                        "content": input_text[:2048],
                    },
                ]
            )
            logger.info(f"image prompt: {image_prompt}")

            if "@edit" in image_prompt:
                is_edit_request = True
                # Download the file from Telegram
                image_bytes = await input_photo.download_as_bytearray()
                # Convert to base64
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                
                # Extract the edit prompt
                edit_prompt = image_prompt
                if '@edit' in image_prompt:
                    edit_prompt = image_prompt.split('@edit')[1].strip()
                
                # Edit the image
                image_b64 = OpenAIChatInterface.edit_image(
                    prompt=edit_prompt,
                    base64_image=base64_image
                )
                # Store image data in chat history
                assistant_msg = ChatMessage(
                    role=Role.ASSISTANT,
                    username="Assistant",
                    type=ChatType.IMAGE,
                    content=input_text,
                    image_b64=image_b64,
                )
                chatHistory.insert(assistant_msg)
                chatHistory.push_msgs_to_s3([user_msg, assistant_msg])
                
                # Decode base64 string to binary
                image_data = base64.b64decode(image_b64)
                # Create an in-memory file-like object
                bio = BytesIO(image_data)
                bio.name = "edited_image.png"  # Name is required for Telegram API
                
                # Send the edited image
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=bio,
                    caption=f"Here's your edited image based on: {edit_prompt}",
                )
        
        # If this is not an edit request, perform vision analysis
        if not is_edit_request:
            out_text = OpenAIChatInterface.chat_vision(
                caption=input_text if input_text else "Describe the image",
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
