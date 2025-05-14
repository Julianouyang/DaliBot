import os
import base64
from io import BytesIO
from PIL import Image

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
        temperature = kwargs.get("temperature", 0.8)
        max_tokens = kwargs.get("max_tokens", 3600)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(f"token used: {response.usage.total_tokens}")
        return response.choices[0].message.content.strip()

    @staticmethod
    def chat_image(*args, **kwargs):
        model = kwargs.get("model", Model().get_current_image_model())
        prompt = kwargs.get("prompt", "")
        n = kwargs.get("n", 1)
        size = kwargs.get("size", "1024x1024")
        quality = kwargs.get("quality", "high")

        response = client.images.generate(
            model=model,
            prompt=prompt,
            n=n,
            size=size,
            quality=quality,
        )
        return response.data[0].b64_json

    @staticmethod
    def edit_image(*args, **kwargs):
        """
        Creates a new image based on the prompt and description of the original image.
        """

        prompt = kwargs.get("prompt", "")
        base64_image = kwargs.get("base64_image", "")
        quality = kwargs.get("quality", "high")

        # Decode the base64 string and load it with PIL
        image_data = base64.b64decode(base64_image)
        img = Image.open(BytesIO(image_data))

        # Ensure the image has an alpha channel so the transparent mask aligns
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Serialize image and mask into in-memory byte buffers
        image_buffer = BytesIO()
        img.save(image_buffer, format="PNG")
        image_buffer.seek(0)

        # Provide a pseudo-filename so the OpenAI SDK infers content type
        image_buffer.name = "image.png"

        try:
            response = client.images.edit(
                model="gpt-image-1",
                image=image_buffer,
                prompt=prompt,
                n=1,
            )
            return response.data[0].b64_json
        except Exception as e:
            logger.error(f"Error editing image: {e}")
            raise e

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
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        )
        logger.info(f"token used: {response.usage.total_tokens}")
        return response.choices[0].message.content
