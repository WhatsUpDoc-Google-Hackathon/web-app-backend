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
from typing import List, Dict

from utils.db_client import DBClient
from utils.custom_types import (
    WebSocketData,
    MessageSender,
    ModelResponse,
    UploadRequest,
    UploadResponse,
    ConversationMessage,
    DocumentMessage,
)
from utils.redis_client import RedisClient
from utils.file_handler import FileHandler
from utils.context_builder import format_conversation_context
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
            logger.info(f"Received message from {user_id}: {data['type']}")

            if data["type"] == "text":
                user_message = data["content"]
            else:
                raise ValueError(f"Invalid message type: {data['type']}")

            # Save user message to DB
            redis_client.save_message(
                session_id, user_id, MessageSender.USER, user_message
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
    redis_health = None
    if redis_client:
        redis_health = redis_client.health_check()
    ai_health = None
    if ai_client:
        try:
            ai_health = ai_client.health_check()
        except Exception as e:
            ai_health = {"status": "unhealthy", "connected": False, "error": str(e)}
    db_health = None
    if db_client:
        db_health = db_client.health_check()
    else:
        db_health = {"status": "not_configured", "connected": False}

    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "services": {
            "api": "running",
            "database": db_health,
            "redis": (
                redis_health
                if redis_health
                else {"status": "not_configured", "connected": False}
            ),
            "ai": (
                ai_health
                if ai_health
                else {"status": "not_configured", "connected": False}
            ),
        },
    }
    logger.info(
        f"Health check requested - DB: {db_health['status']}, Redis: {redis_health['status'] if redis_health else 'not_configured'}, AI: {ai_health['status'] if ai_health else 'not_configured'}"
    )
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
