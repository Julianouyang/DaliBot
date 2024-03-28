from utils import Singleton


class Model(metaclass=Singleton):
    CHAT_MODEL_VISION = "gpt-4-vision-preview"
    CHAT_MODEL_TURBO = "gpt-4-turbo-preview"
    IMAGE_MODEL = "dall-e-3"

    def __init__(self) -> None:
        self.current_chat_model: str
        self.current_image_model: str

    def get_current_chat_model(self):
        return self.current_chat_model

    def get_current_image_model(self):
        return self.current_image_model

    def set_current_chat_model(self, model_name):
        self.current_chat_model = model_name

    def set_current_image_model(self, model_name):
        self.current_image_model = model_name
