from .base import WebhookHandler
from .gemini_service import GeminiService
from .whatsapp_service import WhatsappService
import os
class MessageHandler(WebhookHandler):
    def __init__(self):
        self.gemini_service = GeminiService()
        self.whatsapp_client = WhatsappService(api_url=os.environ.get("WHATSAPP_API_URL"))
    async def handle(self, session_id: str, data: dict):
        print(f"Handling message for session {session_id}: {data}")
        response = self.gemini_service.process(data)
        if response.get("id"):  
          await self.whatsapp_client.send_message(response.get("id"), response.get("text"))
        # Your message handling logic here
