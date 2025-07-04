from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uuid
import datetime
from fastapi.responses import FileResponse

# from utils.ai_client import VertexAIClient
# from utils.stt_client import SpeechToTextStreamer
# from utils.db_client import DBClient
from utils.custom_types import WebSocketData, MessageSender, ModelResponse
from utils.redis_client import RedisClient
import config

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
# ai_client = VertexAIClient()
# db_client = DBClient()
# stt_streamer = SpeechToTextStreamer()
redis_client = RedisClient(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    password=config.REDIS_PASSWORD,
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = websocket.headers.get("user-id", "anonymous")
    session_id = websocket.headers.get("session-id", str(uuid.uuid4()))
    print(f"User ID: {user_id}, Session ID: {session_id}")
    # Create a new session record in DB
    try:
        while True:
            data: WebSocketData = await websocket.receive_json()
            # timestamp = datetime.datetime.utcnow().isoformat()

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

    except WebSocketDisconnect:
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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
