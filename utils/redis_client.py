import redis
import json
import datetime
import logging
from typing import List, Dict, Any, Union, Optional
from .custom_types import MessageSender, ModelResponse

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(
        self,
        host: str = "host.docker.internal",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        test_connection: bool = True,
    ):
        """
        Initialize Redis client

        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            test_connection: Whether to test connection during initialization
        """
        self.connected = False
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            if test_connection:
                # Test connection
                self.client.ping()
                logger.info(f"Successfully connected to Redis at {host}:{port}")
                self.connected = True
            else:
                logger.info(
                    f"Redis client created for {host}:{port} (connection not tested)"
                )
                self.connected = True

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            if test_connection:
                raise
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}")
            self.connected = False
            if test_connection:
                raise

    def _ensure_connection(self) -> bool:
        """
        Ensure Redis connection is available

        Returns:
            bool: True if connected, False otherwise
        """
        if not self.connected:
            return False

        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection lost: {e}")
            self.connected = False
            return False

    def save_message(
        self,
        session_id: str,
        user_id: str,
        sender: MessageSender,
        message: Union[str, ModelResponse],
        s3_doc_url: Optional[str] = None,
    ) -> bool:
        """
        Save a message to Redis conversation log

        Args:
            session_id: Unique session identifier
            user_id: User identifier
            sender: MessageSender enum (USER or IA)
            message: Message content (string for user, ModelResponse for AI)
            s3_doc_url: Optional S3 document URL

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._ensure_connection():
            logger.warning("Cannot save message - Redis not connected")
            return False

        try:
            # Generate timestamp
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"

            # Extract content based on message type
            if isinstance(message, dict) and "content" in message:
                # ModelResponse object
                content = message["content"]
            elif isinstance(message, str):
                # Plain string message
                content = message
            else:
                raise ValueError(f"Invalid message type: {type(message)}")

            # Create message object following the specified format
            message_obj = {
                "role": sender.value,  # "user" or "ai"
                "content": content,
                "timestamp": timestamp,
                "s3_doc_url": s3_doc_url,
            }

            # Redis key format: chat:<session_id>
            key = f"chat:{session_id}"

            # Add message to the list
            result = self.client.lpush(key, json.dumps(message_obj))

            # Set expiry for the conversation (30 days)
            self.client.expire(key, 30 * 24 * 60 * 60)

            logger.info(f"Saved message for session {session_id}, role: {sender.value}")
            return result > 0

        except Exception as e:
            logger.error(f"Error saving message to Redis: {e}")
            return False

    def fetch_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all messages for a session from Redis

        Args:
            session_id: Unique session identifier

        Returns:
            List[Dict]: List of message objects in chronological order (oldest first)
        """
        if not self._ensure_connection():
            logger.warning("Cannot fetch messages - Redis not connected")
            return []

        try:
            key = f"chat:{session_id}"

            # Get all messages from the list (Redis stores in reverse order with lpush)
            raw_messages = self.client.lrange(key, 0, -1)

            if not raw_messages:
                logger.info(f"No messages found for session {session_id}")
                return []

            # Parse JSON messages and reverse to get chronological order
            messages = []
            for raw_msg in reversed(raw_messages):  # Reverse to get oldest first
                try:
                    message = json.loads(raw_msg)
                    messages.append(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing message JSON: {e}")
                    continue

            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages

        except Exception as e:
            logger.error(f"Error fetching messages from Redis: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete all messages for a session

        Args:
            session_id: Unique session identifier

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._ensure_connection():
            logger.warning("Cannot delete session - Redis not connected")
            return False

        try:
            key = f"chat:{session_id}"
            result = self.client.delete(key)
            logger.info(f"Deleted session {session_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting session from Redis: {e}")
            return False

    def get_session_count(self, session_id: str) -> int:
        """
        Get the number of messages in a session

        Args:
            session_id: Unique session identifier

        Returns:
            int: Number of messages in the session
        """
        if not self._ensure_connection():
            logger.warning("Cannot get session count - Redis not connected")
            return 0

        try:
            key = f"chat:{session_id}"
            return self.client.llen(key)
        except Exception as e:
            logger.error(f"Error getting session count from Redis: {e}")
            return 0

    def close(self):
        """Close Redis connection"""
        try:
            if hasattr(self, "client"):
                self.client.close()
                logger.info("Redis connection closed")
                self.connected = False
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Check Redis health status

        Returns:
            Dict with health status information
        """
        try:
            if self._ensure_connection():
                info = self.client.info("server")
                return {
                    "status": "healthy",
                    "connected": True,
                    "redis_version": info.get("redis_version", "unknown"),
                    "uptime": info.get("uptime_in_seconds", 0),
                }
            else:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Connection failed",
                }
        except Exception as e:
            return {"status": "unhealthy", "connected": False, "error": str(e)}
