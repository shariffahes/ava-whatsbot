
import requests
import os
import asyncio
import random

headers = {
    "Content-Type": "application/json",
}

class WhatsappService():
  def __init__(self, api_url: str):
      self.api_url = api_url

  async def go_online_and_type(self, id: str):
      payload = { "chatId": id }
      requests.post(f"{self.api_url}/client/sendPresenceAvailable/{os.environ.get('SESSION_NAME')}", json=payload, headers=headers)
      requests.post(f"{self.api_url}/chat/sendStateTyping/{os.environ.get('SESSION_NAME')}", json={"chatId": id}, headers=headers)

  def stop_typing(self, id: str):
      requests.post(f"{self.api_url}/chat/clearState/{os.environ.get('SESSION_NAME')}", json={"chatId": id}, headers=headers)
  
  def go_offline(self, id: str):
      requests.post(f"{self.api_url}/client/sendPresenceUnAvailable/{os.environ.get('SESSION_NAME')}", json={"chatId": id}, headers=headers)
        
  async def send_message(self, id: str, message: str, media_type: str = None):
      payload = {
          "chatId": id,
          "contentType": "MessageMediaFromURL" if media_type else "string",
          "content": message
      }
      if media_type == "GIF":
        payload['options'] = {
            "sendVideoAsGif": True
        }
      elif media_type == "STICKER":
        payload['options'] = {
            "sendMediaAsSticker": True
        }
      
      print(payload)
      try:
        self.stop_typing(id) 
        response = requests.post(f"{self.api_url}/client/sendMessage/{os.environ.get('SESSION_NAME')}", json=payload, headers=headers)
        
        await asyncio.sleep(random.uniform(0.5, 1.5)) 
        self.go_offline(id)
        
        response.raise_for_status()
        print(f"[WhatsappService] '{message}' sent to {id}")
      except requests.RequestException as e:
          print(f"[WhatsappService] Failed to send message: {e}") 