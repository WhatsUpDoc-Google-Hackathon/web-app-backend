from enum import Enum
from typing_extensions import TypedDict
from typing import Optional, List, Dict


class WebSocketData(TypedDict):
    role: str
    content: Optional[str]
    audio: Optional[str]  # Base64 encoded audio data
    audio_format: Optional[str]
    language_code: Optional[str]


class ConversationContext(TypedDict):
    role: str
    content: str


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


class AudioTranscriptionResult(TypedDict):
    transcript: str
    confidence: float
    words: Optional[List[Dict[str, str]]]


class AudioTranscriptionResponse(TypedDict):
    success: bool
    transcriptions: List[AudioTranscriptionResult]
    language_code: str
    audio_format: str
    error: Optional[str]


class AudioMessage(TypedDict):
    role: str
    content: str  # This will be the transcribed text
    timestamp: str
    audio_format: str
    language_code: str
    transcription_confidence: float
