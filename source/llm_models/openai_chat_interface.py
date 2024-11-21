import os

from constants import Role
from openai import OpenAI
from utils import logger

from .model import Model

client = OpenAI(api_key=os.environ.get("OPENAI_TOKEN"))


class OpenAIChatInterface:
    @staticmethod
    def chat_text(*args, **kwargs):
        model = kwargs.get("model", Model().get_current_chat_model())
        messages = kwargs.get("messages", [])
        temperature = kwargs.get("temperature", 1)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        logger.info(f"token used: {response.usage.total_tokens}")
        return response.choices[0].message.content.strip()

    @staticmethod
    def chat_image(*args, **kwargs):
        model = kwargs.get("model", Model().get_current_image_model())
        prompt = kwargs.get("prompt", "")
        n = kwargs.get("n", 1)
        size = kwargs.get("size", "1024x1024")

        response = client.images.generate(
            model=model,
            prompt=prompt,
            n=n,
            size=size,
        )
        return response.data[0].url

    @staticmethod
    def chat_vision(*args, **kwargs):
        caption = kwargs.get("caption", "")
        image_url = kwargs.get("image_url", "")

        response = client.chat.completions.create(
            model=Model().get_current_chat_model(),
            messages=[
                {
                    "role": Role.USER.value,
                    "content": [
                        {
                            "type": "text",
                            "text": caption,
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        )
        logger.info(f"token used: {response.usage.total_tokens}")
        return response.choices[0].message.content
