import json
import os
from datetime import datetime
from typing import List

import boto3
import tiktoken
from chat import ChatMessage
from constants import Role, system_prompts
from utils import Singleton, logger

from .model import Model

SHORT_MSG_LIMIT = 30

BOT_NAME = os.environ.get("BOT_NAME")
BUCKET = "bot-chat-dali"


class ChatHistory(metaclass=Singleton):
    _instance = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self.short_msgs = []
        self.short_counter = 0

    def insert(self, new_message: ChatMessage):
        self.short_msgs.append(new_message)
        self.short_counter += 1
        if self.short_counter >= SHORT_MSG_LIMIT:
            self.truncate_messages()

    def push_msgs_to_s3(self, msgs: List[ChatMessage]):
        if (
            os.getenv("AWS_ACCESS_KEY_ID") is None
            or os.getenv("AWS_SECRET_ACCESS_KEY") is None
        ):
            logger.error("AWS credentials not found. Skipping storage..")
            return

        s3: boto3.client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        timestamp = datetime.now().strftime("%Y%m%d")

        # List objects within the bucket
        filename = f"{BOT_NAME}/{BOT_NAME}_chat_{timestamp}.json"
        new_msgs_json = json.dumps([m.jsonify_full() for m in msgs], indent=4)
        try:
            # Try to download the existing file from S3
            response = s3.get_object(Bucket=BUCKET, Key=filename)
            existing_data = response["Body"].read().decode("utf-8")
            combined_data = json.loads(existing_data)
            combined_data.extend(json.loads(new_msgs_json))  # Append new data
            final_data = json.dumps(combined_data, indent=4)
        except s3.exceptions.NoSuchKey:
            # If the file does not exist, use new data as the final data
            final_data = new_msgs_json
        s3.put_object(Bucket=BUCKET, Key=filename, Body=final_data)

        # TODO: Add logic to ingest the JSON file into Elasticsearch

    def truncate_messages(self, max_tokens: int = 5120) -> List[dict]:
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
        for message in reversed(self.short_msgs):
            if message.role != Role.SYSTEM:
                total_tokens += len(
                    encoding.encode(json.dumps(message.jsonify_openai()))
                )
                total_messages += 1
                if total_tokens <= max_tokens and total_messages < SHORT_MSG_LIMIT:
                    truncated_messages.insert(0, message)
                else:
                    break
        truncated_messages.insert(
            0,
            ChatMessage(
                role=Role.SYSTEM,
                username="System",
                content=system_prompts.DEFAULT_PROMPT,
            ),
        )

        self.short_msgs = truncated_messages
        self.short_counter = len(self.short_msgs)
        return [m.jsonify_openai() for m in self.short_msgs]

    def reset(self):
        self.short_msgs = []
        self.short_counter = 0
