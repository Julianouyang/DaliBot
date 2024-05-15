from constants import Role
from datetime import datetime
from constants import ChatType


class ChatMessage:
    """
    Arguments:
        role
        username
        content
        timestamp
        type
        image_url
    """

    def __init__(self, **kwargs):
        self.role: Role = kwargs.get("role", None)
        self.username = kwargs.get("username", "")
        self.content = kwargs.get("content", "")
        self.timestamp = kwargs.get(
            "timestamp", datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.type = kwargs.get("type", ChatType.TEXT).value
        self.image_url = kwargs.get("image_url", "")
        self.tokens = kwargs.get("tokens", 0)

    def jsonify_full(self):
        return {
            "role": self.role.value,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp,
            "type": self.type,
            "image_url": self.image_url,
            "tokens": self.tokens,
        }

    def jsonify_openai(self):
        """Return the json needed by openai"""
        return {
            "role": self.role.value,
            "content": self.content,
        }
