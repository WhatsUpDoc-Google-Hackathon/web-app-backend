from dotenv import load_dotenv
import os

load_dotenv()

# GCP project and credentials settings
GCP_PROJECT_ID = "gemma-hcls25par-724"
# GCP Storage bucket name
GCP_STORAGE_BUCKET = "backend-bucket-whatsupdoc"

# Firestore settings
db_collection_sessions = "sessions"
db_collection_messages = "messages"

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Database Configuration for GCP Cloud SQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", 3306)
DB_NAME = os.getenv("DB_NAME", "patients")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_CONNECTION_NAME = os.getenv(
    "DB_CONNECTION_NAME", "gemma-hcls25par-724:europe-west4:backend-db"
)  # For GCP Cloud SQL socket connection

# File handling settings
ALLOWED_FILE_TYPES = {
    "image": ["jpg", "jpeg", "png", "gif", "webp"],
    "audio": ["mp3", "wav", "ogg", "m4a"],
    "document": ["pdf", "txt", "docx", "xlsx", "pptx"],
    "video": ["mp4", "webm", "avi", "mov"],
}
UPLOAD_EXPIRY_SECONDS = 3600  # 1 hour for signed URLs
