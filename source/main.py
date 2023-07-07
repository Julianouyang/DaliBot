import logging
from telegram import Update
from telegram.ext import (
    filters,
    CommandHandler,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
)
import openai
import os
from enum import Enum
from typing import List
import tiktoken
import json

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("Dalibot")


class ROLE(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class DaliBotCore:
    SYSTEM_MSG = "You are a helpful assistant."
    # cache
    msg_cache = []
    # model
    MODEL_NAME = "gpt-4"

    def __init__(self) -> None:
        # Set up OpenAI and Telegram API keys
        openai.api_key = os.environ.get("OPENAI_TOKEN")
        self.telegram_bot_token = os.environ.get("TELEGRAM_TOKEN")

        self.application = ApplicationBuilder().token(self.telegram_bot_token).build()

    def run(self):
        start_handler = CommandHandler("start", DaliBotCore.start_func)
        self.application.add_handler(start_handler)
        reset_handler = CommandHandler("reset", DaliBotCore.reset_func)
        self.application.add_handler(reset_handler)
        system_handler = CommandHandler("system", DaliBotCore.system_func)
        self.application.add_handler(system_handler)
        model_handler = CommandHandler("model", DaliBotCore.set_model)
        self.application.add_handler(model_handler)

        gpt_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND), DaliBotCore.handle_message
        )
        self.application.add_handler(gpt_handler)
        self.application.run_polling()

    @staticmethod
    async def start_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Welcome! I'm a ChatGPT-powered Dalibot.",
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
            DaliBotCore.MODEL_NAME = "gpt-4-0314"
        else:
            DaliBotCore.MODEL_NAME = "gpt-3.5-turbo"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Changing model to {DaliBotCore.MODEL_NAME}")

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # load encoding for model
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(DaliBotCore.MODEL_NAME)

        def gpt_chat_response(text: str) -> str:
            system_messge = [
                {"role": ROLE.SYSTEM.value, "content": DaliBotCore.SYSTEM_MSG}
            ]
            cur_msg = [{"role": ROLE.USER.value, "content": text}]
            messages = truncate_messages(DaliBotCore.msg_cache)

            response = openai.ChatCompletion.create(
                model=DaliBotCore.MODEL_NAME,
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
            response = openai.Image.create(prompt=text, n=1, size="512x512")
            return response["data"][0]["url"]

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

        keywords = ["draw", "image", "picture", "paint"]
        if any(keyword in input_text.lower() for keyword in keywords):
            for keyword in keywords:
                input_text = input_text.lower().replace(keyword, "")
            response = {"type": "image", "content": gpt_image_response(input_text)}
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

def main():
    core = DaliBotCore()
    print("core up and running")
    core.run()


if __name__ == "__main__":
    main()
