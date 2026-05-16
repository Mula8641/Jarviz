"""In-memory conversation history — context injection for LLM."""
from typing import List

class ConversationContext:
    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.turns: List[dict] = []  # {"role": "user"|"assistant", "content": str}

    def add_user(self, text: str):
        self.turns.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        self.turns.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_messages(self, system_prompt: str) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.turns)
        return messages

    def clear(self):
        self.turns = []

    def __len__(self):
        return len(self.turns)