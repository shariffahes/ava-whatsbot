from typing import Dict, Any, List
from rapidfuzz import fuzz, process
from buspal_backend.config.message_config import app_config
from buspal_backend.core.exceptions import MessageProcessingError
import logging

logger = logging.getLogger(__name__)

class MessageProcessor:
    """Handles message processing logic and trigger detection."""
    
    def __init__(self):
        self.config = app_config.message_config
    
    def is_bot_reply_requested(self, message_body: str) -> bool:
        """Check if bot reply is requested based on trigger patterns."""
        try:
            _, score, _ = process.extractOne(
                message_body, 
                self.config.bot_triggers, 
                scorer=fuzz.partial_ratio
            )
            return score >= self.config.bot_trigger_threshold
        except Exception as e:
            logger.error(f"Error checking bot trigger: {e}")
            return False
    
    def is_business_reply_requested(self, message_body: str) -> bool:
        """Check if business reply is requested."""
        return self.config.business_trigger in message_body
    
    def determine_message_count(self, bot_reply: bool, business_reply: bool) -> int:
        """Determine the number of messages to fetch based on request type."""
        if bot_reply:
            return self.config.bot_reply_message_count
        elif business_reply:
            return self.config.business_reply_message_count
        else:
            return self.config.default_message_count
    
    def should_skip_media(self, message_index: int, is_business: bool) -> bool:
        """Determine if media should be skipped for this message."""
        if is_business:
            return False
        return message_index < (self.config.bot_reply_message_count - self.config.media_skip_threshold)
    
    def filter_business_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter messages for business processing."""
        filtered_messages = []
        
        for message in reversed(messages):
            message_data = message.get('_data')
            if message_data and message_data.get('type') == "chat":
                if self.config.business_trigger in message_data.get('body', ''):
                    continue
                else:
                    break
        
        return filtered_messages
    
    def should_process_message(self, bot_reply: bool, business_reply: bool, message_count: int) -> bool:
        """Determine if message should be processed."""
        return message_count > 0 and (bot_reply or business_reply)