import json
from typing import List

import tiktoken
from utils import Singleton

from .model import Model


class ChatHistory(metaclass=Singleton):
    msg_cache = []

    def __init__(self) -> None:
        pass

    @staticmethod
    def insert(item):
        ChatHistory.msg_cache.extend(item)

    @staticmethod
    def truncate_messages(max_tokens: int = 2048, max_messages: int = 8) -> List[dict]:
        total_tokens = 0
        total_messages = 0
        truncated_messages = []

        # load encoding for model
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(Model().get_current_chat_model())

        for message in reversed(ChatHistory.msg_cache):
            total_tokens += len(encoding.encode(json.dumps(message)))
            total_messages += 1
            if total_tokens <= max_tokens and total_messages < max_messages:
                truncated_messages.insert(0, message)
            else:
                break

        return truncated_messages
