from buspal_backend.services.webhooks.base import WebhookHandler
from buspal_backend.services.ai.gemini import GeminiService
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.utils.helpers import fetch_messages, parse_wa_message, get_user_by
from buspal_backend.models.user import UserModel
import os

class MessageHandler(WebhookHandler):
    def __init__(self):
        self.gemini_service = GeminiService()
        self.whatsapp_client = WhatsappService(api_url=os.environ.get("WHATSAPP_API_URL"))
    
    async def handle(self, session_id: str, data: dict):
        # print(f"Handling message for session {session_id}: {data}")

        # # Your message handling logic here
      
        message_data = data.get("message", {}).get("_data", {})
    
        remote_id = message_data.get("from")
        is_group = remote_id.endswith("@g.us")
        s = ""
        if is_group is False or "@bot" not in message_data.get('body', ''):
            return
        
        #get last n messages
        messages = fetch_messages(remote_id)
        if messages is not None:
            formatted_messages = []
            for message in messages:
              msg = parse_wa_message(message)
              if msg.get('sender'):
                id = msg['sender']
                user = UserModel.get_by_id(id)
                if user is None:
                  user = get_user_by(id)
                msg['sender'] = user['name']
                formatted_messages.append(msg)
              else:
                formatted_messages.append({"sender": "BOT", "message": message.get('body', '')}) 
            try:
                text = self.gemini_service.process(formatted_messages)
                print("text", text)
                await self.whatsapp_client.send_message(remote_id, text)
            except Exception as e:
               print("Failed to send to whatsapp ", e)
          
        return {"status": "processed"}