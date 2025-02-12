import base64
import dataclasses
import logging
from typing import List, Optional, Any, Dict, Union
from abc import ABC, abstractmethod

from rest_framework.request import Request

from assistant.bot.models import Instance

logger = logging.getLogger(__name__)


class NoMessageFound(Exception):
    pass


class NoResourceFound(Exception):
    pass


class UnknownUpdate(Exception):
    pass


@dataclasses.dataclass
class User:

    id: str
    username: str = None
    first_name: str = None
    last_name: str = None
    language_code: str = None

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


@dataclasses.dataclass
class CallbackQuery:

    id: str
    from_user: User
    message: str
    data: str

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        data['from_user'] = User.from_dict(data['from_user'])
        return cls(**data)


@dataclasses.dataclass
class Photo:

    file_id: str
    extension: str
    content: bytearray

    def to_dict(self):
        res = dataclasses.asdict(self)
        res['content'] = base64.b64encode(self.content).decode('utf-8')
        return res

    @classmethod
    def from_dict(cls, data: Dict):
        data['content'] = base64.b64decode(data['content'])
        return cls(**data)



@dataclasses.dataclass
class Update:

    chat_id: str
    message_id: Optional[int]
    text: Optional[str]
    photo: Optional[Photo] = None
    user: Optional[User] = None
    callback_query: Optional[CallbackQuery] = None

    def to_dict(self):
        res = dataclasses.asdict(self)
        res['photo'] = self.photo.to_dict() if self.photo else None
        return res

    @classmethod
    def from_dict(cls, data: Dict):
        if data.get('user'):
            data['user'] = User.from_dict(data['user'])
        if data.get('photo'):
            data['photo'] = Photo.from_dict(data['photo'])
        if data.get('callback_query'):
            data['callback_query'] = CallbackQuery.from_dict(data['callback_query'])
        return cls(**data)


@dataclasses.dataclass
class Button:
    text: str
    callback_data: str
    url: str = None


class SingleAnswer:
    text: str
    thinking: str
    image_url: str
    is_markdown: bool
    reply_keyboard: Any
    buttons: List[List[Button]]
    invoice: Dict
    state: Dict
    usage: List[Dict]
    no_store: bool
    debug_info: Dict

    _raw_text: str

    def __init__(self, text: str = None, thinking: str = None, image_url: str = None, is_markdown: bool = False, reply_keyboard: Any = None,
                 buttons: List[List[Button]] = None, state: Dict = None,
                 raw_text: str = None, usage: List[Dict] = None, debug_info: Dict = None, no_store: bool = False):
        self.text = text
        self.thinking = thinking
        self.image_url = image_url
        self.is_markdown = is_markdown
        self.reply_keyboard = reply_keyboard
        self.buttons = buttons
        self.state = state
        self.usage = usage or []
        self.debug_info = debug_info or {}
        self.no_store = no_store
        self._raw_text = raw_text

    @property
    def raw_text(self):
        if self._raw_text:
            return self._raw_text
        return self.text

    @raw_text.setter
    def raw_text(self, value):
        self._raw_text = value

    @property
    def final_model(self):
        return self.usage[-1].get('model') if self.usage else None


class MultiPartAnswer:
    """
    Class to handle multi-part answers, where each part is an instance of Answer.
    """
    parts: List[SingleAnswer]
    no_store: bool
    state: Dict

    def __init__(self, parts: List[SingleAnswer] = None, no_store: bool = False, state: Dict = None):
        self.parts = parts or []
        self.no_store = no_store
        self.state = state or {}

    def add_part(self, answer: SingleAnswer):
        """
        Add a part to the multi-part answer.
        """
        self.parts.append(answer)

    def get_parts(self) -> List[SingleAnswer]:
        """
        Return the list of parts in the multi-part answer.
        """
        return self.parts

    @property
    def no_store(self):
        return all(part.no_store for part in self.parts)

    @no_store.setter
    def no_store(self, value):
        for part in self.parts:
            part.no_store = value


Answer = Union[SingleAnswer, MultiPartAnswer]


class BotPlatform(ABC):

    @abstractmethod
    async def get_update(self, request: Request) -> Update:
        pass

    @abstractmethod
    async def post_answer(self, chat_id: str, answer: SingleAnswer):
        pass

    @abstractmethod
    async def action_typing(self, chat_id):
        pass


class Bot(ABC):

    @abstractmethod
    async def handle_update(self, update: Update) -> SingleAnswer:
        pass

    @abstractmethod
    async def on_answer_sent(self, answer: Answer):
        pass

