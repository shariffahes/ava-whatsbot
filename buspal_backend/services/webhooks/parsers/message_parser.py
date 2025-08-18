from typing import Dict, Any, Optional
from buspal_backend.utils.helpers import parse_wa_message, get_user_by
from buspal_backend.core.exceptions import MessageParsingError, MessageValidationError
from buspal_backend.config.app_config import app_config
import logging

logger = logging.getLogger(__name__)

class MessageParser:
    """Handles extraction and parsing of WhatsApp message data."""
    
    def __init__(self):
        self.config = app_config.message_config
    
    def extract_message_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract message data from webhook payload."""
        try:
            return data.get("message", {}).get("_data", {})
        except Exception as e:
            raise MessageParsingError(f"Failed to extract message data: {e}")
    
    def validate_message_data(self, message_data: Dict[str, Any], message_type: str) -> None:
        """Validate message data and filter unwanted messages."""
        try:
            if message_type == 'message_create':
                me = message_data.get("id", {}).get("fromMe")
                if not me:
                    raise MessageValidationError("Message is not from authenticated user")
                
                bot = not message_data.get('author', None)
                if bot:
                    raise MessageValidationError("Message is from bot")
            
            remote_id = message_data.get('id', {}).get("remote")
            if not remote_id or remote_id == "status@broadcast":
                raise MessageValidationError(f"Invalid remote_id: {remote_id}")
                
        except MessageValidationError:
            raise
        except Exception as e:
            raise MessageValidationError(f"Message validation failed: {e}")
    
    def is_group_message(self, remote_id: str) -> bool:
        """Check if message is from a group chat."""
        return remote_id.endswith(self.config.group_suffix)
    
    def extract_message_body(self, message_data: Dict[str, Any]) -> str:
        """Extract message body based on message type."""
        if message_data.get('type') == 'image':
            return message_data.get('caption', '')
        return message_data.get('body', '')
    
    async def format_message(self, message: Dict[str, Any], convo_id: str, skip_media: bool = False, is_group: bool = True) -> Optional[Dict[str, Any]]:
        """Format a single message with sender information."""
        try:
            msg = await parse_wa_message(message, skip_media, is_dm=not is_group)
            
            if msg.get('sender'):
                user = await get_user_by(msg['sender'], convo_id)
                if user and user.get('name'):
                    msg['sender'] = user['name']
                else:
                    logger.warning(f"User not found for sender: {msg['sender']}")
                    msg['sender'] = "Unknown User"
            else:
                msg = {
                    "sender": "BOT", 
                    "message": message.get("body", "")
                }
            return msg
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            raise MessageParsingError(f"Failed to format message: {e}")
    
    def get_remote_id(self, message_data: Dict[str, Any]) -> str:
        """Extract remote ID from message data."""
        remote_id = message_data.get('id', {}).get("remote")
        if not remote_id:
            raise MessageParsingError("No remote ID found in message data")
        return remote_id