import json
from typing import List
from datetime import datetime
import tiktoken
from utils import Singleton

from .model import Model
from constants import Role, system_prompts

SHORT_MSG_LIMIT = 12
LONG_MSG_LIMIT = 36
SYSTEM_MESSAGE = {"role": Role.SYSTEM.value, "content": system_prompts.DEFAULT_PROMPT}


class ChatMessage:
    def __init__(self, role, username, content, timestamp):
        self.role: Role = role
        self.username = username
        self.content = content
        self.timestamp = timestamp

    def jsonify(self):
        return {
            "role": self.role.value,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    def jsonify_openai(self):
        """Return the json needed by openai"""
        return {
            "role": self.role.value,
            "content": self.content,
        }


class ChatHistory(metaclass=Singleton):
    short_msgs = []
    long_msgs = []
    # The limit for appending messages to current conversation
    short_counter = 0
    # The limit for writing out json files and reset
    long_counter = 0

    def __init__(self) -> None:
        pass

    @staticmethod
    def insert(new_message):
        ChatHistory.short_msgs.extend(new_message)
        ChatHistory.short_counter += 1
        if ChatHistory.short_counter >= SHORT_MSG_LIMIT:
            ChatHistory.truncate_messages()

        ChatHistory.long_msgs.extend(new_message)
        ChatHistory.long_counter += 1
        if ChatHistory.long_counter >= LONG_MSG_LIMIT:
            ChatHistory.convert_to_json_and_reset()

    @staticmethod
    def convert_to_json_and_reset():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Convert messages to JSON and save to file
        with open(f"chat_history_{timestamp}.json", "w") as f:
            json.dump(ChatHistory.long_msgs, f, indent=4)

        # Reset the counter and messages
        ChatHistory.long_counter = 0
        ChatHistory.long_msgs = 0

        # TODO: Add logic to ingest the JSON file into Elasticsearch

    @staticmethod
    def truncate_messages(max_tokens: int = 2560) -> List[dict]:
        """Truncate messages if exceed the limit.
        However, this should not truncate system prompt.
        """
        total_tokens = 0
        total_messages = 0
        truncated_messages = []

        # load encoding for model
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(Model().get_current_chat_model())

        # avoid modify system prompt
        for message in reversed(ChatHistory.short_msgs):
            if message["role"] != Role.SYSTEM.value:
                total_tokens += len(encoding.encode(json.dumps(message)))
                total_messages += 1
                if total_tokens <= max_tokens and total_messages < SHORT_MSG_LIMIT:
                    truncated_messages.insert(0, message)
                else:
                    break
        truncated_messages.insert(0, SYSTEM_MESSAGE)
        # assign back to ChatHistory.short_msgs
        ChatHistory.short_msgs = truncated_messages
        return truncated_messages

    def reset():
        ...
        # if long_msgs has sth, dump to json first
