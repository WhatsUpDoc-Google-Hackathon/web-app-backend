from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uuid
import datetime
import logging
import sys
from fastapi.responses import FileResponse

# from utils.ai_client import VertexAIClient
# from utils.db_client import DBClient
from utils.custom_types import WebSocketData, MessageSender, ModelResponse
from utils.redis_client import RedisClient
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

# Initialize clients with error handling
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

# db_client = DBClient()
# stt_streamer = SpeechToTextStreamer()

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
                ai_result = ai_client.predict(user_message)
                ai_response: ModelResponse = {
                    "type": "text",
                    "content": ai_result.get("prediction") if ai_result else "AI error",
                    "meta": {
                        "source": "vertex_ai",
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                        "success": ai_result.get("success", False) if ai_result else False,
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
        messages = redis_client.fetch_session_messages(session_id)
        transformed_messages = redis_client.format_conversation_messages(messages)
        print(f"Session {session_id} ended with {len(messages)} messages")
        # report = ai_client.generate_report(transformed_messages)
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

    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "services": {
            "api": "running",
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
        f"Health check requested - Redis: {redis_health['status'] if redis_health else 'not_configured'}, AI: {ai_health['status'] if ai_health else 'not_configured'}"
    )
    return health_status


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
