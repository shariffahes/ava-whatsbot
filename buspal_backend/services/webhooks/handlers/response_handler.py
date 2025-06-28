from typing import Dict, Any
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.services.ai.gemini_service import GeminiService
from buspal_backend.services.storage.conversation_storage import ConversationStorage
from buspal_backend.core.exceptions import WhatsAppServiceError, AIServiceError
import logging

logger = logging.getLogger(__name__)

class ResponseHandler:
    """Handles AI response generation and WhatsApp message sending."""
    
    def __init__(self, whatsapp_service: WhatsappService, gemini_service: GeminiService):
        self.whatsapp_service = whatsapp_service
        self.gemini_service = gemini_service
        self.storage = ConversationStorage(gemini_service)
    
    async def handle_bot_reply(self, remote_id: str, messages: list) -> None:
        """Generate and send bot reply."""
        try:
            logger.info(f"Generating bot reply for {remote_id}")
            
            # Get conversation context
            context = self.storage.get_conversation_context(remote_id)
            
            # Generate AI response
            response = await self.gemini_service.process(messages, context, remote_id)
            
            logger.debug(f"AI response: {response}")
            
            # Send text response
            if response.get('text'):
                await self.whatsapp_service.send_message(remote_id, response['text'])
            
            # Send media response
            if response.get('media') and response['media'].get('url'):
                url = response['media']['url']
                media_type = response['media']['type']
                await self.whatsapp_service.send_message(remote_id, url, media_type)
            
            logger.info(f"Bot reply sent to {remote_id}")
            
        except AIServiceError as e:
            logger.error(f"AI service error for {remote_id}: {e}")
            await self._send_error_message(remote_id, "I'm having trouble understanding your request.")
        except WhatsAppServiceError as e:
            logger.error(f"WhatsApp service error for {remote_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in bot reply for {remote_id}: {e}")
            await self._send_error_message(remote_id, "Sorry, something went wrong.")
    
    async def handle_business_reply(self, remote_id: str, messages: list) -> None:
        """Generate and send business reply."""
        try:
            logger.info(f"Generating business reply for {remote_id}")
            
            response_text = await self.gemini_service.process_business(messages)
            
            if response_text:
                await self.whatsapp_service.send_message(remote_id, response_text)
                logger.info(f"Business reply sent to {remote_id}")
            else:
                logger.warning(f"Empty response from Gemini service for {remote_id}")
                
        except AIServiceError as e:
            logger.error(f"AI service error for business reply {remote_id}: {e}")
            await self._send_error_message(remote_id, "I couldn't process your business request.")
        except WhatsAppServiceError as e:
            logger.error(f"WhatsApp service error for business reply {remote_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate business reply for {remote_id}: {e}")
            await self._send_error_message(remote_id, "Sorry, I'm having trouble processing your business request.")
    
    async def _send_error_message(self, remote_id: str, message: str) -> None:
        """Send error message to user."""
        try:
            await self.whatsapp_service.send_message(remote_id, message)
        except Exception as send_error:
            logger.error(f"Failed to send error message to {remote_id}: {send_error}")
    
    async def set_typing_status(self, remote_id: str, is_typing: bool = True) -> None:
        """Set typing status for better user experience."""
        try:
            if is_typing:
                await self.whatsapp_service.go_online_and_type(remote_id)
            else:
                await self.whatsapp_service.stop_typing(remote_id)
                await self.whatsapp_service.go_offline(remote_id)
        except Exception as e:
            logger.warning(f"Failed to set typing status for {remote_id}: {e}")