from enum import Enum
from typing import TypedDict


class WebSocketData(TypedDict):
    type: str
    content: str


class MessageSender(Enum):
    USER = "user"
    IA = "ai"


class ModelMetadata(TypedDict):
    source: str
    timestamp: str


class ModelResponse(TypedDict):
    type: str
    content: str
    meta: ModelMetadata
