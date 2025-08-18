from typing import Dict, Any, List
from rapidfuzz import fuzz, process
from buspal_backend.config.app_config import app_config
from buspal_backend.core.exceptions import MessageProcessingError
import logging
import os
logger = logging.getLogger(__name__)

class MessageProcessor:
    """Handles message processing logic and trigger detection."""
    
    def __init__(self):
        self.config = app_config.message_config
    
    def is_bot_reply_requested(self, message_body: str) -> bool:
        """Check if bot reply is requested based on trigger patterns."""
        try:
            if os.environ.get("ENV") == "DEV":
                # In development, we use a specific local bot trigger
                return self.config.bot_triggers in message_body # type: ignore
            
            _, score, _ = process.extractOne(
                message_body, 
                self.config.bot_triggers, 
                scorer=fuzz.partial_ratio
            )
            return score >= self.config.bot_trigger_threshold
        except Exception as e:
            logger.error(f"Error checking bot trigger: {e}")
            return False
    
    def determine_message_count(self, bot_reply: bool) -> int:
        """Determine the number of messages to fetch based on request type."""
        if bot_reply:
            return self.config.bot_reply_message_count
        else:
            return self.config.default_message_count
    
    def should_skip_media(self, message_index: int) -> bool:
        """Determine if media should be skipped for this message. Threshold to reduce media processing."""
        return message_index < (self.config.bot_reply_message_count - self.config.media_skip_threshold)
    
    def should_process_message(self, bot_reply: bool, message_count: int) -> bool:
        """Determine if message should be processed."""
        return message_count > 0 and bot_reply