from buspal_backend.services.webhooks.base import WebhookHandler
from buspal_backend.services.ai.gemini import GeminiService
from buspal_backend.services.ai.inference import InferenceService
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.utils.helpers import fetch_messages, parse_wa_message, get_user_by
from buspal_backend.models.group import GroupModel
import os

class MessageHandler(WebhookHandler):
    def __init__(self):
        self.gemini_service = GeminiService()
        self.whatsapp_client = WhatsappService(api_url=os.environ.get("WHATSAPP_API_URL"))
    
    async def handle(self, data: dict):
        message_data = data.get("message", {}).get("_data", {})
    
        remote_id = message_data.get("from")
        is_group = remote_id.endswith("@g.us")

        if is_group == False:
          return
        
        bot_reply = "@bot" in message_data.get('body', '')
        n = 1
        if bot_reply:
          n = 25
        #get last n messages
        messages = fetch_messages(remote_id, n)
        if messages is not None:
            formatted_messages = []
            for message in messages:
              msg = parse_wa_message(message)
              if msg.get('sender'):
                id = msg['sender']
                user = get_user_by(id)
                msg['sender'] = user['name']
                formatted_messages.append(msg)
              else:
                formatted_messages.append({"sender": "BOT", "message": message.get("body", "")}) 
            try:
                if bot_reply:
                  text = self.gemini_service.process(formatted_messages)
                  print("text", text)
                  await self.whatsapp_client.send_message(remote_id, text)
                # else:
                #   group = get_user_by(remote_id, True)
                #   if len(group["messages"]) >= 3:
                #     inference = InferenceService()
                #     summary = inference.generate_content(group["messages"] + formatted_messages)
                #     group["summaries"].append(summary)
                #     GroupModel.update_by_id(remote_id, {"summaries": group["summaries"], "messages": []})
                #   else:
                #     print(formatted_messages)
                #     group["messages"].extend(formatted_messages)
                #     GroupModel.update_by_id(remote_id, {"messages": group["messages"]})
            except Exception as e:
               print("Failed to send to whatsapp ", e)
          
        return {"status": "processed"}