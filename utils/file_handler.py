import base64
import boto3
import hashlib
import io
import mimetypes
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from PIL import Image

import config


class FileHandler:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION,
        )
        self.bucket_name = config.S3_BUCKET_NAME

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

    async def upload_to_s3(self, file_data: bytes, filename: str, user_id: str) -> Dict:
        """Upload file to S3 and return file info with URL."""
        try:
            file_info = self.get_file_info(filename, file_data)
            file_id = self.generate_file_id(filename, user_id)

            # Create S3 key with organized structure
            s3_key = f"chat-files/{user_id}/{datetime.utcnow().strftime('%Y/%m')}/{file_id}_{filename}"

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=file_info["mime_type"],
                Metadata={
                    "user_id": user_id,
                    "original_filename": filename,
                    "file_id": file_id,
                },
            )

            # Generate signed URL for access
            signed_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=config.UPLOAD_EXPIRY_SECONDS,
            )

            # For images, create and upload thumbnail
            thumbnail_url = None
            if file_info["type"] == "image":
                thumbnail_url = await self._upload_thumbnail(file_data, s3_key, user_id)

            return {
                "file_id": file_id,
                "filename": filename,
                "size": file_info["size"],
                "type": file_info["type"],
                "mime_type": file_info["mime_type"],
                "url": signed_url,
                "thumbnail_url": thumbnail_url,
                "s3_key": s3_key,
                "storage_type": "s3",
            }

        except Exception as e:
            raise ValueError(f"Error uploading to S3: {str(e)}")

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

    async def _upload_thumbnail(
        self, image_data: bytes, original_s3_key: str, user_id: str
    ) -> Optional[str]:
        """Create and upload thumbnail to S3."""
        try:
            thumbnail_data = self._create_thumbnail(image_data)
            if not thumbnail_data:
                return None

            # Create thumbnail S3 key
            thumbnail_key = original_s3_key.replace(
                f"/{user_id}/", f"/{user_id}/thumbnails/"
            ).replace(".", "_thumb.")

            # Upload thumbnail
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=thumbnail_key,
                Body=thumbnail_data,
                ContentType="image/jpeg",
            )

            # Generate signed URL for thumbnail
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": thumbnail_key},
                ExpiresIn=config.UPLOAD_EXPIRY_SECONDS,
            )
        except Exception:
            return None

    async def get_signed_upload_url(self, filename: str, user_id: str) -> Dict:
        """Generate a signed URL for direct client upload to S3."""
        file_id = self.generate_file_id(filename, user_id)
        s3_key = f"chat-files/{user_id}/{datetime.utcnow().strftime('%Y/%m')}/{file_id}_{filename}"

        # Generate presigned POST URL
        presigned_post = self.s3_client.generate_presigned_post(
            Bucket=self.bucket_name,
            Key=s3_key,
            Fields={"acl": "private"},
            Conditions=[
                {"acl": "private"},
                ["content-length-range", 1, 100 * 1024 * 1024],  # 100MB max
            ],
            ExpiresIn=300,  # 5 minutes
        )

        return {
            "file_id": file_id,
            "upload_url": presigned_post["url"],
            "fields": presigned_post["fields"],
            "s3_key": s3_key,
        }
