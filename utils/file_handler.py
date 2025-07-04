import hashlib
import io
import mimetypes
import os
from datetime import datetime
from typing import Dict, Tuple, Optional
from PIL import Image
from google.cloud import storage

import config


class FileHandler:
    def __init__(self):
        # GCP Storage client
        try:
            self.gcp_client = storage.Client(project=config.GCP_PROJECT_ID)
            self.gcp_bucket_name = config.GCP_STORAGE_BUCKET
            self.gcp_bucket = self.gcp_client.bucket(self.gcp_bucket_name)
        except Exception as e:
            print(f"Warning: Failed to initialize GCP Storage client: {e}")
            self.gcp_client = None

    def get_file_info(self, filename: str, file_data: bytes) -> Dict:
        """Extract file information."""
        file_extension = filename.split(".")[-1].lower()
        file_size = len(file_data)

        # Determine file type category
        file_type = None
        for category, extensions in config.ALLOWED_FILE_TYPES.items():
            if file_extension in extensions:
                file_type = category
                break

        if not file_type:
            raise ValueError(f"Unsupported file type: {file_extension}")

        return {
            "filename": filename,
            "size": file_size,
            "type": file_type,
            "extension": file_extension,
            "mime_type": mimetypes.guess_type(filename)[0]
            or "application/octet-stream",
        }

    def generate_file_id(self, filename: str, user_id: str) -> str:
        """Generate a unique file ID."""
        timestamp = datetime.utcnow().isoformat()
        content = f"{filename}_{user_id}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()

    async def upload_to_gcp_storage(
        self, file_data: bytes, filename: str, session_id: str, user_id: str
    ) -> Dict:
        """Upload file to GCP Storage and return file info with URL."""
        try:
            file_info = self.get_file_info(filename, file_data)
            file_id = self.generate_file_id(filename, user_id)

            # Create GCP Storage object path with organized structure
            blob_path = f"{session_id}/{filename}"

            # Upload to GCP Storage
            blob = self.gcp_bucket.blob(blob_path)
            blob.upload_from_string(file_data, content_type=file_info["mime_type"])

            # Set metadata
            blob.metadata = {
                "user_id": user_id,
                "session_id": session_id,
                "original_filename": filename,
                "file_id": file_id,
            }
            blob.patch()

            # Generate public URL (Firebase Storage style)
            public_url = f"https://firebase.storage/bucket/{self.gcp_bucket_name}/{session_id}/{filename}"

            return {
                "file_id": file_id,
                "filename": filename,
                "size": file_info["size"],
                "type": file_info["type"],
                "mime_type": file_info["mime_type"],
                "url": public_url,
                "blob_path": blob_path,
                "storage_type": "gcp",
            }

        except Exception as e:
            raise ValueError(f"Error uploading to GCP Storage: {str(e)}")

    def _create_thumbnail(
        self, image_data: bytes, max_size: Tuple[int, int] = (200, 200)
    ) -> Optional[bytes]:
        """Create a thumbnail from image data and return as bytes."""
        try:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Convert to RGB if necessary
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            # Save as JPEG
            thumbnail_io = io.BytesIO()
            image.save(thumbnail_io, format="JPEG", quality=85)
            return thumbnail_io.getvalue()
        except Exception:
            return None

    async def upload_thumbnail_to_gcp(
        self, image_data: bytes, original_blob_path: str, session_id: str
    ) -> Optional[str]:
        """Create and upload thumbnail to GCP Storage."""
        try:
            thumbnail_data = self._create_thumbnail(image_data)
            if not thumbnail_data:
                return None

            # Create thumbnail blob path
            thumbnail_path = (
                f"{session_id}/thumbnails/{original_blob_path.split('/')[-1]}"
            )
            thumbnail_path = thumbnail_path.replace(".", "_thumb.")

            # Upload thumbnail
            thumbnail_blob = self.gcp_bucket.blob(thumbnail_path)
            thumbnail_blob.upload_from_string(thumbnail_data, content_type="image/jpeg")

            # Generate public URL for thumbnail
            return f"https://firebase.storage/bucket/{self.gcp_bucket_name}/{thumbnail_path}"
        except Exception:
            return None
