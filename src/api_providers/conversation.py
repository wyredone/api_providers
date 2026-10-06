"""Portable chat documents. Failed/cancelled turns never become future context."""
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .types import AIError


def validate_messages(messages):
    if not isinstance(messages, list):
        raise AIError("Messages must be a list.", "configuration")
    result = []
    expected = "user"
    for item in messages:
        if not isinstance(item, dict) or item.get("role") != expected:
            raise AIError("Chat messages must alternate user and assistant roles.", "configuration")
        if not isinstance(item.get("content"), str) or not item["content"].strip():
            raise AIError("Chat messages must contain nonempty text.", "configuration")
        result.append({"role": item["role"], "content": item["content"]})
        expected = "assistant" if expected == "user" else "user"
    return result


class Conversation:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.title = "New chat"
        self.messages = []

    def request_messages(self, prompt):
        if not isinstance(prompt, str) or not prompt.strip():
            raise AIError("Prompt cannot be empty.", "configuration")
        return validate_messages(self.messages + [{"role": "user", "content": prompt.strip()}])

    def complete_turn(self, prompt, answer):
        updated = validate_messages(self.request_messages(prompt) + [{"role": "assistant", "content": answer}])
        self.messages = updated
        if self.title == "New chat":
            self.title = prompt.strip().splitlines()[0][:70]

    def clear(self):
        self.messages = []
        self.title = "New chat"

    def save(self, path):
        data = {"format": "api-providers-chat", "version": 1, "id": self.id,
                "created_at": self.created_at, "title": self.title, "messages": self.messages}
        target = Path(path)
        fd, name = tempfile.mkstemp(dir=target.parent, prefix=".chat-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != "api-providers-chat" or data.get("version") != 1:
                raise ValueError()
            messages = validate_messages(data.get("messages"))
            if messages and messages[-1]["role"] != "assistant":
                raise ValueError()
            if not all(isinstance(data.get(k), str) for k in ("id", "created_at", "title")):
                raise ValueError()
            chat = cls()
            chat.id, chat.created_at, chat.title = data["id"], data["created_at"], data["title"]
            chat.messages = messages
            return chat
        except (ValueError, OSError, AIError) as exc:
            raise AIError("Invalid chat file; current conversation was preserved.", "configuration") from exc
