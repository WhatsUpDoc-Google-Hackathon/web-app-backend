from dotenv import load_dotenv
import os

load_dotenv()

# Add your GCP project and credentials settings here
GCP_PROJECT_ID = "your-gcp-project-id"
# Path to your service account JSON
GOOGLE_APPLICATION_CREDENTIALS = "/path/to/credentials.json"
# Firestore settings
db_collection_sessions = "sessions"
db_collection_messages = "messages"

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Vertex AI settings
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_REGION = os.getenv("VERTEX_REGION", "")
MODELS_CONFIG_PATH = os.getenv("MODELS_CONFIG_PATH", "models.config")

# File handling settings
ALLOWED_FILE_TYPES = {
    "image": ["jpg", "jpeg", "png", "gif", "webp"],
    "audio": ["mp3", "wav", "ogg", "m4a"],
    "document": ["pdf", "txt", "docx", "xlsx", "pptx"],
    "video": ["mp4", "webm", "avi", "mov"],
}
UPLOAD_EXPIRY_SECONDS = 3600  # 1 hour for signed URLs
