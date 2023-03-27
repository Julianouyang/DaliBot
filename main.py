import logging
from telegram import Update
from telegram.ext import (
    filters,
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    ApplicationBuilder,
    ContextTypes,
)
import openai
import os


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Welcome! I'm a ChatGPT-powered Dalibot."
    )


def text_davinci_response(text: str) -> str:
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=text,
        max_tokens=2048,
        n=1,
        stop=None,
        temperature=0.5,
    )
    return response.choices[0].text.strip()


def gpt_turbo_response(text: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": text}],
    )
    return response.choices[0].message.content.strip()


def gpt_image_response(text: str) -> str:
    response = openai.Image.create(prompt=text, n=1, size="512x512")
    return response["data"][0]["url"]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_text = update.message.text

    keywords = ["draw", "image", "picture", "paint"]
    if any(keyword in input_text.lower() for keyword in keywords):
        for keyword in keywords:
            input_text = input_text.lower().replace(keyword, "")
        response = {"type": "image", "content": gpt_image_response(input_text)}
    else:
        response = {"type": "text", "content": gpt_turbo_response(input_text)}

    if response["type"] == "text":
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=response["content"]
        )
    else:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id, photo=response["content"]
        )


def main():
    # Set up OpenAI and Telegram API keys
    openai.api_key = os.environ.get("OPENAI_TOKEN")
    telegram_bot_token = os.environ.get("TELEGRAM_TOKEN")

    application = ApplicationBuilder().token(telegram_bot_token).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    gpt_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(gpt_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
