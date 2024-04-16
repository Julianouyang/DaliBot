import json
import os
from datetime import datetime
from typing import List

import boto3
import tiktoken
from chat import ChatMessage
from constants import Role, system_prompts
from utils import Singleton

from .model import Model

SHORT_MSG_LIMIT = 20
LONG_MSG_LIMIT = 8

BOT_NAME = os.environ.get("BOT_NAME")


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
    def insert(new_message: ChatMessage):
        ChatHistory.short_msgs.append(new_message)
        ChatHistory.short_counter += 1
        if ChatHistory.short_counter >= SHORT_MSG_LIMIT:
            ChatHistory.truncate_messages()

        ChatHistory.long_msgs.append(new_message)
        ChatHistory.long_counter += 1
        if ChatHistory.long_counter >= LONG_MSG_LIMIT:
            ChatHistory.convert_to_json_and_reset()

    @staticmethod
    def convert_to_json_and_reset():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Convert messages to JSON and save to file
        # with open(f"chat_history_{timestamp}.json", "w") as f:
        #     json.dump(ChatHistory.long_msgs, f, indent=4)
        # Create an S3 resource
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Your S3 bucket name
        bucket_name = "bot-chat-dali"

        # List objects within the bucket
        filename = f"data/{BOT_NAME}_history_{timestamp}.json"
        msgs_json = json.dumps(ChatHistory.long_msgs, indent=4)
        s3.put_object(Bucket=bucket_name, Key=filename, Body=msgs_json)

        # Reset the counter and messages
        ChatHistory.long_counter = 0
        ChatHistory.long_msgs = []

        # TODO: Add logic to ingest the JSON file into Elasticsearch

    @staticmethod
    def truncate_messages(max_tokens: int = 5120) -> List[dict]:
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
        message: ChatMessage
        for message in reversed(ChatHistory.short_msgs):
            if message.role != Role.SYSTEM.value:
                total_tokens += len(
                    encoding.encode(json.dumps(message.jsonify_openai()))
                )
                total_messages += 1
                if total_tokens <= max_tokens and total_messages < SHORT_MSG_LIMIT:
                    truncated_messages.insert(0, message.jsonify_openai())
                else:
                    break
        truncated_messages.insert(
            0, ChatMessage(Role.SYSTEM.value, "System", system_prompts).jsonify_openai()
        )
        # assign back to ChatHistory.short_msgs
        ChatHistory.short_msgs = truncated_messages
        return truncated_messages

    def reset():
        ...
        # if long_msgs has sth, dump to json first
