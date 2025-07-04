# Add your GCP project and credentials settings here
GCP_PROJECT_ID = "your-gcp-project-id"
# Path to your service account JSON
GOOGLE_APPLICATION_CREDENTIALS = "/path/to/credentials.json"
# Firestore settings
db_collection_sessions = "sessions"
db_collection_messages = "messages"

# S3 Configuration
AWS_ACCESS_KEY_ID = "your-aws-access-key"
AWS_SECRET_ACCESS_KEY = "your-aws-secret-key"
AWS_REGION = "us-east-1"
S3_BUCKET_NAME = "your-chat-files-bucket"

# File handling settings
ALLOWED_FILE_TYPES = {
    "image": ["jpg", "jpeg", "png", "gif", "webp"],
    "audio": ["mp3", "wav", "ogg", "m4a"],
    "document": ["pdf", "txt", "docx", "xlsx", "pptx"],
    "video": ["mp4", "webm", "avi", "mov"],
}
UPLOAD_EXPIRY_SECONDS = 3600  # 1 hour for signed URLs
