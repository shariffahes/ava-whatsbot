from typing import Dict, Any, List, Optional
from buspal_backend.models.conversation import ConversationModel
from buspal_backend.services.ai.ai_provider import AIProvider
from buspal_backend.services.ai.ai_service_factory import AIServiceFactory
from buspal_backend.types.enums import AIMode
from buspal_backend.utils.helpers import get_user_by
from buspal_backend.core.exceptions import ConversationStorageError
from buspal_backend.config.app_config import app_config
import json
import logging

logger = logging.getLogger(__name__)

class ConversationStorage:
    """Handles conversation storage and summarization logic."""
    
    def __init__(self):
        self.ai_service = AIServiceFactory.get_service(AIMode.BUDDY, "gemini")
        self.config = app_config.message_config
    
    async def store_message_and_summarize(self, remote_id: str, messages: List[Dict[str, Any]]) -> None:
        """Store messages and handle summarization when threshold is reached."""
        try:
            conversation = await get_user_by(remote_id)
            current_message_count = len(conversation.get("messages", []))
            
            if current_message_count >= self.config.summary_message_threshold:
                await self._create_summary_and_reset(remote_id, conversation)
            else:
                await self._store_latest_message(remote_id, messages)
                
        except Exception as e:
            logger.error(f"Error in message storage for {remote_id}: {e}")
            raise ConversationStorageError(f"Failed to store conversation: {e}")
    
    async def _create_summary_and_reset(self, remote_id: str, conversation: Dict[str, Any]) -> None:
        """Create summary and reset message history."""
        try:
            result = await self.ai_service.generate_completion(conversation["messages"], "SUMMARY")
            response = json.loads(result)
            
            logger.debug(f"Summary generated for {remote_id}: {result}")
            
            # Store summary
            ConversationModel.update_by_id(remote_id, {
                "summaries": {
                    "content": response.get('content'),
                    "participants": response.get('participants'),
                    "start_date": response.get('start_date'),
                    "end_date": response.get('end_date')
                }
            }, "$push")
            
            # Reset messages
            ConversationModel.update_by_id(remote_id, {"messages": []})
            
        except Exception as e:
            raise ConversationStorageError(f"Failed to create summary: {e}")
    
    async def _store_latest_message(self, remote_id: str, messages: List[Dict[str, Any]]) -> None:
        """Store the latest message."""
        try:
            if not messages:
                return
            
            last_index = len(messages) - 1
            if last_index < 0:
                return
            logger.debug(f"Adding message for {remote_id}")
            ConversationModel.update_by_id(
                remote_id, 
                {"messages": messages[last_index]}, 
                "$push"
            )
            
        except Exception as e:
            raise ConversationStorageError(f"Failed to store message: {e}")
    
    def get_conversation_context(self, remote_id: str) -> Optional[str]:
        """Retrieve conversation context for AI processing."""
        try:
            conversation = ConversationModel.get_by_id(remote_id)
            
            if not conversation or not conversation.get('summaries'):
                return None
            
            last_15_summaries = '\n'.join(
                f"{json.dumps(summary)}" 
                for summary in conversation['summaries'][-15:]
            )
            
            return f"#History:\n{last_15_summaries}"
            
        except Exception as e:
            logger.error(f"Error retrieving context for {remote_id}: {e}")
            return None