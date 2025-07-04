from enum import Enum
from typing import TypedDict, Optional


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


class ConversationMessage(TypedDict):
    role: str
    content: str
    timestamp: str
    s3_doc_url: Optional[str]


class Document(TypedDict):
    name: str
    url: str


class ModelReportRequest(TypedDict):
    conversation: list[ConversationMessage]
    documents: Optional[list[Document]]
