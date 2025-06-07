from buspal_backend.services.webhooks.base import WebhookHandler
from buspal_backend.services.ai.gemini import GeminiService
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.utils.helpers import fetch_messages, parse_wa_message, get_user_by
from typing import Dict, List, Optional, Any
import os
import logging

logger = logging.getLogger(__name__)
class MessageHandler(WebhookHandler):
    """Handles incoming WhatsApp messages and processes them with AI services."""
    
    # Constants
    DEFAULT_MESSAGE_COUNT = 0
    BOT_REPLY_MESSAGE_COUNT = 10
    BUSINESS_REPLY_MESSAGE_COUNT = 30
    BOT_TRIGGER = "@bot"
    BUSINESS_TRIGGER = "@business"
    GROUP_SUFFIX = "@g.us"
  
    def __init__(self):
        try:
          self.gemini_service = GeminiService()
          self.whatsapp_client = WhatsappService(
            api_url=os.environ.get("WHATSAPP_API_URL")
          )
        except Exception as e:
          logger.error(f"Failed to initialize MessageHandler: {e}")
          raise
    
    async def handle(self, data: Dict[str, Any], type) -> Dict[str, str]:
        """
        Handle incoming webhook data and process WhatsApp messages.
        
        Args:
            data: Webhook data containing message information
            
        Returns:
            Dict indicating processing status
        """
        try:
          message_data = self._extract_message_data(data)
          if type == 'message_create':
              me = message_data.get("id", {}).get("fromMe")
              if not me:
                return
              bot = not message_data.get('author', None)
              if bot:
                return
            
          if not message_data:
            logger.warning("No valid message data found in webhook")
            return {"status": "no_message_data"}
          
          remote_id = message_data.get('id').get("remote")
          if not remote_id:
            logger.warning("No sender ID found in message data")
            return {"status": "no_sender"}
          
          # Only process group messages
          # if not self._is_group_message(remote_id):
          #   logger.debug(f"Ignoring non-group message from {remote_id}")
          #   return {"status": "not_group_message"}
          
          await self._process_group_message(message_data, remote_id)
          return {"status": "processed"}
            
        except Exception as e:
          logger.error(f"Error handling webhook data: {e}", exc_info=True)
          return {"status": "error"}

    def _extract_message_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
      return data.get("message", {}).get("_data", {})
      
    def _is_group_message(self, remote_id: str) -> bool:
        return remote_id.endswith(self.GROUP_SUFFIX)
    
    def _is_bot_reply_requested(self, message_body: str) -> bool:
        return self.BOT_TRIGGER in message_body
    
    async def _process_group_message(self, message_data: Dict[str, Any], remote_id: str) -> None:
        """Process a group message and handle bot replies or message storage."""
        message_body = message_data.get('caption', '') if message_data.get('type') == 'image' else message_data.get('body', '')
        bot_reply_requested = self._is_bot_reply_requested(message_body)
        business_reply_requested = self.BUSINESS_TRIGGER in message_body
        message_count = (
            self.BOT_REPLY_MESSAGE_COUNT if bot_reply_requested 
            else self.BUSINESS_REPLY_MESSAGE_COUNT if business_reply_requested 
            else self.DEFAULT_MESSAGE_COUNT
        )

        if message_count == 0:
            return
        
        logger.info(f"Processing message from {remote_id}, bot_reply: {bot_reply_requested}")
        
        # Fetch and format messages
        messages = self._fetch_and_format_messages(remote_id, message_count, business_reply_requested)
        if not messages:
            logger.warning(f"No messages found for {remote_id}")
            return
        if bot_reply_requested:
            await self._handle_bot_reply(remote_id, messages)
        elif business_reply_requested:
            await self._handle_business_reply(remote_id, messages)
        else:
            self._handle_message_storage(remote_id, messages)
    
    def _fetch_and_format_messages(self, remote_id: str, count: int, is_business: bool = False) -> List[Dict[str, Any]]:
        """Fetch and format recent messages from the group."""
        try:
            messages = fetch_messages(remote_id, count)
            if not messages:
                return []
            formatted_messages = []
            if is_business:
               messages.reverse()
            for idx, message in enumerate(messages):
                message_data = message.get('_data')
                if is_business:
                    if message_data['type'] == "chat":
                        if '@business' in message_data['body']:
                            continue
                        else:
                            break
                skip_media = True if is_business == False and idx < 5 else False
                formatted_msg = self._format_message(message_data, skip_media, is_group=self._is_group_message(remote_id))
                if formatted_msg:
                    formatted_messages.append(formatted_msg)
            print(formatted_messages)
            logger.debug(f"Formatted {len(formatted_messages)} messages for {remote_id}")
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Error fetching messages for {remote_id}: {e}")
            return []
    
    def _format_message(self, message: Dict[str, Any], skip_media: bool = False, is_group: bool = True) -> Optional[Dict[str, Any]]:
        """Format a single message with sender information."""
        try:
            msg = parse_wa_message(message, skip_media, is_dm= not is_group)
            if msg.get('sender'):
                user = get_user_by(msg['sender'])
                if user and user.get('name'):
                    msg['sender'] = user['name']
                else:
                    logger.warning(f"User not found for sender: {msg['sender']}")
                    msg['sender'] = "Unknown User"
            else:
                # Handle bot messages
                msg = {
                    "sender": "BOT", 
                    "message": message.get("body", "")
                }
            return msg
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return None
    
    async def _handle_business_reply(self, remote_id: str, messages: List[Dict[str, Any]]) -> None:
        try:
          logger.info(f"Generating business reply for {remote_id}")
          response_text = self.gemini_service.process_business(messages)
          
          if response_text:
              await self.whatsapp_client.send_message(remote_id, response_text)
              logger.info(f"Business reply sent to {remote_id}")
          else:
              logger.warning(f"Empty response from Gemini service for {remote_id}")
                
        except Exception as e:
            logger.error(f"Failed to generate or send bot reply to {remote_id}: {e}")
            try:
                await self.whatsapp_client.send_message(
                    remote_id, 
                    "Sorry, I'm having trouble processing your request right now."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
     
    async def _handle_bot_reply(self, remote_id: str, messages: List[Dict[str, Any]]) -> None:
      """Handle bot reply generation and sending."""
      try:
        logger.info(f"Generating bot reply for {remote_id}")
        response_text = self.gemini_service.process(messages)
        
        if response_text:
            await self.whatsapp_client.send_message(remote_id, response_text)
            logger.info(f"Bot reply sent to {remote_id}")
        else:
            logger.warning(f"Empty response from Gemini service for {remote_id}")
              
      except Exception as e:
          logger.error(f"Failed to generate or send bot reply to {remote_id}: {e}")
          try:
              await self.whatsapp_client.send_message(
                  remote_id, 
                  "Sorry, I'm having trouble processing your request right now."
              )
          except Exception as send_error:
              logger.error(f"Failed to send error message: {send_error}")
    
    def _handle_message_storage(self, remote_id: str, messages: List[Dict[str, Any]]) -> None:
        """Handle message storage and potential summarization (commented out logic)."""
        try:
            # This is where the commented summarization logic would go
            # For now, just log that we would store the messages
            logger.debug(f"Would store {len(messages)} messages for {remote_id}")
            
            # Uncomment and modify as needed:
            # group = get_user_by(remote_id, True)
            # if len(group.get("messages", [])) >= 3:
            #     inference = InferenceService()
            #     summary = inference.generate_content(group["messages"] + messages)
            #     summaries = group.get("summaries", [])
            #     summaries.append(summary)
            #     GroupModel.update_by_id(remote_id, {
            #         "summaries": summaries, 
            #         "messages": []
            #     })
            # else:
            #     existing_messages = group.get("messages", [])
            #     existing_messages.extend(messages)
            #     GroupModel.update_by_id(remote_id, {"messages": existing_messages})
            
        except Exception as e:
            logger.error(f"Error in message storage for {remote_id}: {e}")