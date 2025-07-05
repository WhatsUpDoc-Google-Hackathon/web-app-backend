from typing import Dict, List
from utils.custom_types import ConversationMessage, ChatMessage, MessageSender


def retrieve_document_content(s3_doc_url: str) -> str:
    """
    Retrieve document content from local file system based on S3 URL pattern

    Args:
        s3_doc_url: URL in format that maps to ./files/{session_id}/{user_id}/{filename}

    Returns:
        str: Base64 encoded content of the file
    """
    try:
        # Extract path components from S3 URL
        # Assuming URL format contains session/user-id/filename pattern
        url_parts = s3_doc_url.split("/")

        # Find the session/user-id/filename pattern in the URL
        for i, part in enumerate(url_parts):
            if i + 2 < len(url_parts):
                session_id = part
                user_id = url_parts[i + 1]
                filename = url_parts[i + 2]

                # Construct local file path
                local_path = f"./files/{session_id}/{user_id}/{filename}"

                # Read file content and encode as base64
                with open(local_path, "rb") as file:
                    file_content = file.read()
                    import base64

                    return base64.b64encode(file_content).decode("utf-8")

        raise FileNotFoundError(f"Could not extract file path from URL: {s3_doc_url}")

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {str(e)}")
    except Exception as e:
        raise Exception(f"Error retrieving document content: {str(e)}")


def format_conversation_context(
    conversation_context: Dict[str, List[ConversationMessage]],
) -> List[ChatMessage]:
    """
    Format conversation context for AI model
    """
    conversation_context = []
    for message in conversation_context:
        if message["role"] == MessageSender.UPLOAD:
            # Handle image upload - create image_url structure
            conversation_context.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": message["content"]}}
                    ],
                }
            )
        else:
            # Handle regular text messages
            conversation_context.append(
                {
                    "role": message["role"],
                    "content": [
                        {
                            "type": "text",
                            "text": message["content"],
                        }
                    ],
                }
            )

    return conversation_context
