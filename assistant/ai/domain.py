from dataclasses import dataclass
from typing import Union, Dict, TypedDict


@dataclass
class AIResponse:
    result: Union[str, Dict]  # depends on response_format (json or text)
    usage: Dict = None
    length_limited: bool = False

    @property
    def model(self):
        return self.usage['model'] if self.usage else None


class Message(TypedDict):
    role: str
    content: str


def user_message(content: str):
    return Message(role='user', content=content)


def assistant_message(content: str):
    return Message(role='assistant', content=content)


def system_message(content: str):
    return Message(role='system', content=content)
