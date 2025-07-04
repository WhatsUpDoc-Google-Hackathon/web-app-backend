from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
import uuid
import datetime
import logging
import sys
import base64
from fastapi.responses import FileResponse
from typing import List, Dict, Any

from utils.db_client import DBClient
from utils.custom_types import (
    WebSocketData,
    MessageSender,
    ModelResponse,
    UploadRequest,
    UploadResponse,
    ConversationMessage,
    DocumentMessage,
    AudioMessage,
    AudioTranscriptionResponse,
)
from utils.redis_client import RedisClient
from utils.file_handler import FileHandler
from utils.context_builder import format_conversation_context
from utils.stt_client import STTClient
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from utils.ai_client import VertexClient

    logger.info("Attempting to initialize AI client...")
    logger.info("AI client configuration:")
    logger.info(f"  Models config path: {config.MODELS_CONFIG_PATH}")
    logger.info(f"  Project ID: {config.VERTEX_PROJECT_ID}")
    logger.info(f"  Default region: {config.VERTEX_REGION}")

    ai_client = VertexClient(
        config_path=config.MODELS_CONFIG_PATH,
        project_id=config.VERTEX_PROJECT_ID,
        default_region=config.VERTEX_REGION,
        auto_initialize=True,
    )
    logger.info("AI client initialized successfully")
except Exception as e:
    ai_client = None
    logger.error(f"Failed to initialize AI client: {e}")
    logger.warning("Continuing without AI client - using mock responses")

db_client = None
try:
    logger.info("Attempting to connect to MySQL database...")
    db_client = DBClient()
    logger.info("Database client initialized successfully")
except Exception as e:
    logger.error(f"Failed to connect to database: {e}")
    logger.warning("Continuing without database - some endpoints will not work")

file_handler = FileHandler()

redis_client = None
try:
    logger.info("Attempting to connect to Redis...")
    redis_client = RedisClient(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        test_connection=True,
    )
    logger.info("Redis client initialized successfully")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    logger.warning("Continuing without Redis - message persistence disabled")

stt_client = None
try:
    logger.info("Attempting to initialize Speech-to-Text client...")
    stt_client = STTClient(
        project_id=config.GCP_PROJECT_ID,
        language_code="en-US",
        auto_initialize=True,
    )
    logger.info("Speech-to-Text client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Speech-to-Text client: {e}")
    logger.warning("Continuing without STT - audio transcription disabled")


def build_conversation_context(
    session_id: str,
) -> Dict[str, List[ConversationMessage]]:
    """
    Build conversation context for AI model from Redis messages

    Args:
        session_id: Unique session identifier

    Returns:
        Dict containing conversation array formatted for AI model
    """
    if not redis_client:
        logger.warning("Redis client not available - returning empty conversation")
        return {"conversation": []}

    try:
        messages = redis_client.fetch_session_messages(session_id)
        logger.info(
            f"Built conversation context with {len(messages)} messages for session {session_id}"
        )
        return {"conversation": messages}

    except Exception as e:
        logger.error(f"Error building conversation context: {e}")
        return {"conversation": []}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = websocket.headers.get("user-id", "anonymous")
    session_id = websocket.headers.get("session-id", str(uuid.uuid4()))
    logger.info(
        f"WebSocket connection established - User ID: {user_id}, Session ID: {session_id}"
    )

    try:
        while True:
            data: WebSocketData = await websocket.receive_json()
            logger.info(
                f"Received message from {user_id}: role={data.get('role')}, has_content={bool(data.get('content'))}, has_audio={bool(data.get('audio'))}"
            )

            # Validate message format
            has_content = (
                data.get("content") is not None and data.get("content").strip()
            )
            has_audio = data.get("audio") is not None and data.get("audio").strip()

            # Handle text message
            if has_content and not has_audio:
                user_message = data["content"]
                # Save user message to Redis
                if redis_client:
                    redis_client.save_message(
                        session_id, user_id, MessageSender.USER, user_message
                    )
            # Handle audio message
            elif has_audio and not has_content:
                # Handle audio transcription
                if not stt_client:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "Speech-to-Text service not available",
                            "meta": {
                                "source": "server",
                                "timestamp": datetime.datetime.utcnow().isoformat()
                                + "Z",
                            },
                        }
                    )
                    continue

                # Transcribe audio - default to webm for browser recordings
                audio_format = data.get("audio_format", "webm")
                language_code = data.get("language_code", "en-US")

                transcription_result = stt_client.transcribe_base64_audio(
                    base64_audio=data["audio"],
                    audio_format=audio_format,
                    language_code=language_code,
                )

                if not transcription_result["success"]:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": f"Transcription failed: {transcription_result.get('error', 'Unknown error')}",
                            "meta": {
                                "source": "stt",
                                "timestamp": datetime.datetime.utcnow().isoformat()
                                + "Z",
                            },
                        }
                    )
                    continue

                # Get the best transcription
                transcriptions = transcription_result.get("transcriptions", [])
                if not transcriptions:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "No transcription results",
                            "meta": {
                                "source": "stt",
                                "timestamp": datetime.datetime.utcnow().isoformat()
                                + "Z",
                            },
                        }
                    )
                    continue

                best_transcription = transcriptions[0]
                user_message = best_transcription["transcript"]
                confidence = best_transcription["confidence"]

                # Save audio message to Redis
                if redis_client:
                    audio_msg: AudioMessage = {
                        "role": "user",
                        "content": user_message,
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                        "audio_format": audio_format,
                        "language_code": language_code,
                        "transcription_confidence": confidence,
                    }
                    redis_client.save_message(
                        session_id, user_id, MessageSender.AUDIO, audio_msg
                    )

                # Send transcription result back to client
                await websocket.send_json(
                    {
                        "type": "transcription",
                        "content": user_message,
                        "meta": {
                            "source": "stt",
                            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                            "confidence": confidence,
                            "audio_format": audio_format,
                            "language_code": language_code,
                        },
                    }
                )

            elif has_content and has_audio:
                raise ValueError(
                    "Invalid message format: cannot have both 'content' and 'audio' in the same message"
                )
            else:
                raise ValueError(
                    "Invalid message format: must have either 'content' (text) or 'audio' (base64 encoded)"
                )

            # Send message to AI if available, else mock
            if ai_client:
                # Build conversation context for AI
                conversation_context = build_conversation_context(session_id)
                ctx = format_conversation_context(conversation_context)
                logger.info(f"Conversation context: {len(conversation_context)}")
                ai_result = ai_client.predict(user_message, ctx)
                
                ai_response: ModelResponse = {
                    "type": "text",
                    "content": ai_result.get("prediction") if ai_result else "AI error",
                    "meta": {
                        "source": ai_result.get("model_id", "unknown"),
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                        "success": (
                            ai_result.get("success", False) if ai_result else False
                        ),
                    },
                }
            else:
                # Create a mock AI response for testing
                ai_response: ModelResponse = {
                    "type": "text",
                    "content": f"Echo: {user_message}",
                    "meta": {
                        "source": "mock_ai",
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    },
                }

            if redis_client:
                # Save AI response to DB
                redis_client.save_message(
                    session_id, user_id, MessageSender.IA, ai_response
                )

            # Send response back to client
            await websocket.send_json(ai_response)
            logger.info(f"Sent response to {user_id}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}, session {session_id}")
        # On disconnect, trigger final report generation
        conversation_context = build_conversation_context(session_id)
        print(
            f"Session {session_id} ended with {len(conversation_context['conversation'])} messages"
        )
        # report = ai_client.generate_report(conversation_context)
        # Convert report from Markdown to PDF
        # report_pdf = convert_markdown_to_pdf(report, "report.pdf")
        # Upload report to GCP Storage
        # report_pdf_url = await file_handler.upload_to_gcp_storage(
        #     file_data=report_pdf,
        #     filename=f"{session_id}_report.pdf",
        #     session_id=session_id,
        #     user_id=user_id,
        # )
        # db_client.save_report(session_id, report)
        print("WebSocket disconnected")


@app.get("/cors")
async def cors():
    return FileResponse("cors.json")


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run liveness probe"""
    try:
        redis_health = redis_client.health_check()
    except Exception as e:
        redis_health = {"status": "unhealthy", "connected": False, "error": str(e)}
    try:
        ai_health = ai_client.health_check()
    except Exception as e:
            ai_health = {"status": "unhealthy", "connected": False, "error": str(e)}
    try:
        db_health = db_client.health_check()
    except Exception as e:
        db_health = {"status": "unhealthy", "connected": False, "error": str(e)}
    try:
        stt_health = stt_client.health_check()
    except Exception as e:
        stt_health = {"status": "unhealthy", "connected": False, "error": str(e)}

    health_status = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "services": {
            "api": "running",
            "database": db_health,
            "redis": redis_health,
            "ai": ai_health,
            "stt": stt_health,
        },
    }
    logger.info(f"Health check requested - {health_status}")
    return health_status


@app.post("/upload")
async def upload(upload_request: UploadRequest) -> UploadResponse:
    """Upload a document to GCP Storage and save to Redis"""
    try:
        # Decode base64 content
        try:
            file_content = base64.b64decode(upload_request["content_base64"])
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid base64 content: {str(e)}"
            )

        # Upload to GCP Storage
        upload_result = await file_handler.upload_to_gcp_storage(
            file_data=file_content,
            filename=upload_request["filename"],
            session_id=upload_request["session_id"],
            user_id=upload_request["user_id"],
        )

        # Save to Redis if available
        if redis_client:
            img_msg: DocumentMessage = {
                "role": "user",
                "content": upload_result["blob_path"],
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
            redis_client.save_message(
                upload_request["session_id"],
                upload_request["user_id"],
                MessageSender.UPLOAD,
                img_msg,
            )

        # Return response
        response: UploadResponse = {
            "status": "success",
            "s3_url": upload_result["url"],
            "message": "Document uploaded successfully",
        }

        logger.info(
            f"Document {upload_request['filename']} uploaded successfully for user {upload_request['user_id']}"
        )
        return response

    except ValueError as e:
        logger.error(f"Upload validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during upload"
        )


@app.get("/patients")
async def get_all_patients():
    """Get all patients with their latest reports for the table view"""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        patients = db_client.get_all_patients_with_latest_reports()
        return {"status": "success", "data": patients, "count": len(patients)}
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch patients")


@app.get("/patients/{patient_id}")
async def get_patient_details(patient_id: str):
    """Get patient details by ID"""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        patient = db_client.get_patient_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        return {"status": "success", "data": patient}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch patient")


@app.get("/patients/{patient_id}/reports")
async def get_patient_reports(patient_id: str):
    """Get all reports for a patient (timeline view)"""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # First check if patient exists
        patient = db_client.get_patient_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        reports = db_client.get_patient_reports_timeline(patient_id)
        return {
            "status": "success",
            "data": {"patient": patient, "reports": reports},
            "count": len(reports),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching reports for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch patient reports")


@app.get("/reports/{report_id}")
async def get_report_details(report_id: str):
    """Get specific report details by ID"""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        report = db_client.get_report_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Also get patient info for context
        patient = db_client.get_patient_by_id(report["patient_id"])

        return {"status": "success", "data": {"report": report, "patient": patient}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch report")


@app.get("/stt/config")
async def get_stt_config():
    """Get Speech-to-Text configuration and supported formats/languages"""
    if not stt_client:
        raise HTTPException(
            status_code=503, detail="Speech-to-Text service not available"
        )

    try:
        return {
            "status": "success",
            "data": {
                "supported_formats": stt_client.get_supported_formats(),
                "supported_languages": stt_client.get_supported_languages(),
                "default_language": stt_client.language_code,
                "project_id": stt_client.project_id,
                "connected": stt_client.connected,
            },
        }
    except Exception as e:
        logger.error(f"Error getting STT config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get STT configuration")


@app.post("/stt/transcribe")
async def transcribe_audio(request: Dict[str, Any]):
    """Test endpoint for audio transcription"""
    if not stt_client:
        raise HTTPException(
            status_code=503, detail="Speech-to-Text service not available"
        )

    try:
        # Validate request
        if "audio_base64" not in request:
            raise HTTPException(status_code=400, detail="Missing audio_base64 field")

        audio_format = request.get("audio_format", "wav")
        language_code = request.get("language_code", "en-US")

        # Transcribe audio
        result = stt_client.transcribe_base64_audio(
            base64_audio=request["audio_base64"],
            audio_format=audio_format,
            language_code=language_code,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Transcription failed: {result.get('error', 'Unknown error')}",
            )

        return {
            "status": "success",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during transcription"
        )


@app.get("/ws/format")
async def websocket_message_format():
    """Get WebSocket message format documentation"""
    return {
        "status": "success",
        "message": "WebSocket message format documentation",
        "formats": {
            "text_message": {
                "role": "user",
                "content": "Hello, this is a text message",
                "audio": None,
                "audio_format": None,
                "language_code": None,
            },
            "audio_message": {
                "role": "user",
                "content": None,
                "audio": "base64_encoded_audio_data",
                "audio_format": "webm",  # Optional: webm, wav, mp3, ogg, m4a
                "language_code": "en-US",  # Optional: default is en-US
            },
        },
        "supported_audio_formats": ["webm", "wav", "mp3", "ogg", "m4a"],
        "supported_languages": [
            "en-US",
            "en-GB",
            "es-ES",
            "fr-FR",
            "de-DE",
            "it-IT",
            "pt-BR",
            "ja-JP",
            "ko-KR",
            "zh-CN",
            "zh-TW",
            "ar-SA",
            "hi-IN",
            "ru-RU",
            "nl-NL",
            "sv-SE",
            "da-DK",
            "no-NO",
            "fi-FI",
        ],
        "notes": [
            "For text messages: provide 'content' field, leave 'audio' as null",
            "For audio messages: provide 'audio' field with base64 encoded data, leave 'content' as null",
            "Cannot have both 'content' and 'audio' in the same message",
            "Browser recordings are typically in 'webm' format",
            "Audio transcription confidence score is returned with transcription results",
        ],
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Web App Backend API",
        "status": "running",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
