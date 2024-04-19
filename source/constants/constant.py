from enum import Enum


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatType(Enum):
    TEXT = "text"
    IMAGE = "image"
