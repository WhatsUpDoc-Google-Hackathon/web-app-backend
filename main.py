from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uuid
import datetime
import logging
import sys
from fastapi.responses import FileResponse

# from utils.ai_client import VertexAIClient
# from utils.stt_client import SpeechToTextStreamer
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
# ai_client = VertexAIClient()
# db_client = DBClient()
# stt_streamer = SpeechToTextStreamer()

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

            # # Send message to AI
            # ai_response: ModelResponse = ai_client.chat(user_message)

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
        print(f"Session {session_id} ended with {len(messages)} messages")
        # report = ai_client.generate_report(messages)
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
        },
    }
    logger.info(
        f"Health check requested - Redis: {redis_health['status'] if redis_health else 'not_configured'}"
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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
