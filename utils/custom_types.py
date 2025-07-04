from enum import Enum
from typing_extensions import TypedDict
from typing import Optional, List


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
    conversation: List[ConversationMessage]
    documents: Optional[List[Document]]


class UploadRequest(TypedDict):
    session_id: str
    user_id: str
    filename: str
    content_base64: str


class UploadResponse(TypedDict):
    status: str
    s3_url: str
    message: str


class DocumentMessage(TypedDict):
    role: str
    content: str
    timestamp: str
    s3_doc_url: str
