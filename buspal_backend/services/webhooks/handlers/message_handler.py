from typing import Dict, Any, List, Optional
from buspal_backend.services.ai.ai_service_factory import AIServiceFactory
from buspal_backend.services.webhooks.base import WebhookHandler
from buspal_backend.services.webhooks.parsers.message_parser import MessageParser
from buspal_backend.services.webhooks.processors.message_processor import MessageProcessor
from buspal_backend.services.webhooks.handlers.response_handler import ResponseHandler
from buspal_backend.services.storage.conversation_storage import ConversationStorage
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.utils.helpers import fetch_messages
from buspal_backend.types.enums import AIMode
from buspal_backend.core.exceptions import (
    MessageProcessingError, 
    MessageParsingError, 
    MessageValidationError
)
from buspal_backend.config.app_config import app_config
from buspal_backend.models.conversation import ConversationModel
import asyncio
import logging

logger = logging.getLogger(__name__)

class MessageHandler(WebhookHandler): 
    def __init__(self):
        try:
            # Initialize services
            self.whatsapp_service = WhatsappService(
                api_url=app_config.whatsapp_config.api_url
            )
            # Initialize components
            self.parser = MessageParser()
            self.processor = MessageProcessor()
            self.mode = AIMode.BUDDY
            
        except Exception as e:
            logger.error(f"Failed to initialize MessageHandler: {e}")
            raise MessageProcessingError(f"Handler initialization failed: {e}")
    
    async def handle(self, data: Dict[str, Any], message_type: str) -> Dict[str, str]:
        remote_id = None
        
        try:
            # Parse and validate message
            message_data = self.parser.extract_message_data(data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                return {"status": "no_message_data"}
            
            self.parser.validate_message_data(message_data, message_type)
            remote_id = self.parser.get_remote_id(message_data)
            convo = ConversationModel.get_by_id(remote_id)
            mode = convo.get('mode', None) # type: ignore
            self.mode = AIMode(mode if mode else AIMode.BUDDY.value)

            # Initialize other services after conversation mode is determined
            self.ai_service = AIServiceFactory.get_service(self.mode)
            
            self.response_handler = ResponseHandler(
                self.whatsapp_service, 
                self.ai_service
            )
            self.storage = ConversationStorage(self.ai_service)

            # Process message
            await self._process_message(message_data, remote_id)
            
            return {"status": "processed"}
            
        except MessageValidationError as e:
            logger.info(f"Message validation failed: {e}")
            return {"status": "validation_failed"}
        except MessageParsingError as e:
            logger.error(f"Message parsing failed: {e}")
            return {"status": "parsing_failed"}
        except Exception as e:
            logger.error(f"Error handling webhook data: {e}", exc_info=True)
            await self._cleanup_on_error(remote_id)
            return {"status": "error"}
    
    async def _process_message(self, message_data: Dict[str, Any], remote_id: str) -> None:
        """Process the message based on its type and triggers."""
        try:
            # Extract message body and determine request types
            message_body = self.parser.extract_message_body(message_data)
            bot_reply_requested = self.processor.is_bot_reply_requested(message_body)

            # Determine message count to fetch
            message_count = self.processor.determine_message_count(
                bot_reply_requested
            )

            logger.info(f"Processing message from {remote_id}, bot_reply: {bot_reply_requested}")
            
            # Fetch and format messages
            messages = await self._fetch_and_format_messages(
                remote_id, 
                message_count
            )
            
            if not messages:
                logger.warning(f"No messages found for {remote_id}")
                return

            # Store messages asynchronously
            asyncio.create_task(
                self.storage.store_message_and_summarize(remote_id, messages)
            )
            
            if not self.processor.should_process_message(
                bot_reply_requested,  
                message_count
            ):
                return
            
            # Handle responses
            if bot_reply_requested:
                await self.response_handler.set_typing_status(remote_id, True)
                await self.response_handler.handle_bot_reply(remote_id, messages)
  
        except Exception as e:
            logger.error(f"Error processing message for {remote_id}: {e}")
            raise MessageProcessingError(f"Message processing failed: {e}")
    
    async def _fetch_and_format_messages(
        self, 
        remote_id: str, 
        count: int
    ) -> List[Dict[str, Any]]:
        """Fetch and format recent messages from the group."""
        try:
            messages = await fetch_messages(remote_id, count)
            if not messages:
                return []
            
            formatted_messages = []
            is_group = self.parser.is_group_message(remote_id)
            
            # Format each message
            for idx, message in enumerate(messages):
                message_data = message.get('_data')
                if not message_data:
                    continue
                
                skip_media = self.processor.should_skip_media(idx)
                formatted_msg = await self.parser.format_message(
                    message_data,
                    remote_id,
                    skip_media, 
                    is_group
                )
                
                if formatted_msg:
                    formatted_messages.append(formatted_msg)
            
            logger.debug(f"Formatted {len(formatted_messages)} messages for {remote_id}")
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Error fetching messages for {remote_id}: {e}")
            raise MessageProcessingError(f"Failed to fetch messages: {e}")
    
    async def _cleanup_on_error(self, remote_id: Optional[str]) -> None:
        """Cleanup resources on error."""
        if remote_id:
            try:
                await self.response_handler.set_typing_status(remote_id, False)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup for {remote_id}: {cleanup_error}")