from constants import Role


class ChatMessage:
    def __init__(self, role=None, username="", content="", timestamp=""):
        self.role: Role = role
        self.username = username
        self.content = content
        self.timestamp = timestamp

    def jsonify_full(self):
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
