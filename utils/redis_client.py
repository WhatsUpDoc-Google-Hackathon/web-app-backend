import redis
import json
import datetime
from typing import List, Dict, Any, Union, Optional
from .custom_types import MessageSender, ModelResponse


class RedisClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        """
        Initialize Redis client

        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
        """
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self.client.ping()
            print(f"Successfully connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            print(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            print(f"Error initializing Redis client: {e}")
            raise

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

            print(f"Saved message for session {session_id}, role: {sender.value}")
            return result > 0

        except Exception as e:
            print(f"Error saving message to Redis: {e}")
            return False

    def fetch_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all messages for a session from Redis

        Args:
            session_id: Unique session identifier

        Returns:
            List[Dict]: List of message objects in chronological order (oldest first)
        """
        try:
            key = f"chat:{session_id}"

            # Get all messages from the list (Redis stores in reverse order with lpush)
            raw_messages = self.client.lrange(key, 0, -1)

            if not raw_messages:
                print(f"No messages found for session {session_id}")
                return []

            # Parse JSON messages and reverse to get chronological order
            messages = []
            for raw_msg in reversed(raw_messages):  # Reverse to get oldest first
                try:
                    message = json.loads(raw_msg)
                    messages.append(message)
                except json.JSONDecodeError as e:
                    print(f"Error parsing message JSON: {e}")
                    continue

            print(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages

        except Exception as e:
            print(f"Error fetching messages from Redis: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete all messages for a session

        Args:
            session_id: Unique session identifier

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = f"chat:{session_id}"
            result = self.client.delete(key)
            print(f"Deleted session {session_id}")
            return result > 0
        except Exception as e:
            print(f"Error deleting session from Redis: {e}")
            return False

    def get_session_count(self, session_id: str) -> int:
        """
        Get the number of messages in a session

        Args:
            session_id: Unique session identifier

        Returns:
            int: Number of messages in the session
        """
        try:
            key = f"chat:{session_id}"
            return self.client.llen(key)
        except Exception as e:
            print(f"Error getting session count from Redis: {e}")
            return 0

    def close(self):
        """Close Redis connection"""
        try:
            self.client.close()
            print("Redis connection closed")
        except Exception as e:
            print(f"Error closing Redis connection: {e}")
