from enum import Enum
from typing_extensions import TypedDict
from typing import Optional, List, Union, Dict


class WebSocketData(TypedDict):
    type: str
    content: str


class ConversationContext(TypedDict):
    role: str
    content: str


# New OpenAI-style conversation structure
class ContentPart(TypedDict):
    type: str  # "text" or "image_url"
    text: Optional[str]  # For text content
    image_url: Optional[Dict[str, str]]  # For image content


class ChatMessage(TypedDict):
    role: str  # "user" or "assistant"
    content: Union[
        str, List[ContentPart]
    ]  # Can be simple string or list of content parts


class MessageSender(Enum):
    USER = "user"
    IA = "ai"
    UPLOAD = "upload"


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
