from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uuid
import datetime

import config
from utils.ai_client import VertexAIClient
from utils.stt_client import SpeechToTextStreamer
from utils.db_client import DBClient

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
ai_client = VertexAIClient()
db_client = DBClient()
stt_streamer = SpeechToTextStreamer()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    user_id = websocket.headers.get("user-id", "anonymous")
    # Create a new session record in DB
    db_client.create_session(session_id, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            # data format: { type: 'text'|'audio', content: text|string(base64) }
            timestamp = datetime.datetime.utcnow().isoformat()

            if data["type"] == "audio":
                # TODO: Implement streaming recognition
                # transcript = await stt_streamer.transcribe_stream(data['content'])
                transcript = "[TRANSCRIBED TEXT]"  # placeholder
                user_message = transcript
            else:
                user_message = data["content"]

            # Save user message to DB
            db_client.save_message(session_id, user_id, "user", user_message, timestamp)

            # Send message to AI
            ai_response = ai_client.chat(user_message)

            # Save AI response to DB
            db_client.save_message(
                session_id,
                user_id,
                "ai",
                ai_response,
                datetime.datetime.utcnow().isoformat(),
            )

            # Send response back to client
            await websocket.send_json({"type": "ai", "content": ai_response})

    except WebSocketDisconnect:
        # On disconnect, trigger final report generation
        # messages = db_client.fetch_session_messages(session_id)
        # report = ai_client.generate_report(messages)
        # db_client.save_report(session_id, report)
        pass


# ----------------------- utils/ai_client.py -----------------------
# from google.cloud import aiplatform
def ______():
    pass


# TODO: Implement VertexAIClient:
# - chat(prompt: str) -> str
# - generate_report(messages: List[Dict]) -> str
# Use google-cloud-aiplatform or vertexai.preview.language_models


# ----------------------- utils/stt_client.py -----------------------
# from google.cloud import speech
def ______():
    pass


# TODO: Implement SpeechToTextStreamer:
# - transcribe_stream(audio_chunks: List[bytes]) -> str
# Use streaming_recognize on audio chunks for low latency


# ----------------------- utils/db_client.py -----------------------
# from google.cloud import firestore
def ______():
    pass


# TODO: Implement DBClient:
# - create_session(session_id, user_id)
# - save_message(session_id, user_id, role, content, timestamp)
# - fetch_session_messages(session_id) -> List[Dict]
# - save_report(session_id, report_text)
