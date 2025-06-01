
import requests
import os
import asyncio
import random

class WhatsappService():
  def __init__(self, api_url: str):
      self.api_url = api_url

  async def send_message(self, id: str, message: str):
      payload = {
          "chatId": id,
          "contentType": "string",
          "content": message
      }

      headers = {
          "Content-Type": "application/json",
      }

      try:
        await asyncio.sleep(random.uniform(0.5, 1)) 
        response = requests.post(f"{self.api_url}/client/sendPresenceAvailable/{os.environ.get('SESSION_NAME')}", json=payload, headers=headers)
        
        await asyncio.sleep(random.uniform(1, 3)) 
        response = requests.post(f"{self.api_url}/chat/sendStateTyping/{os.environ.get('SESSION_NAME')}", json={"chatId": id}, headers=headers)
        
        await asyncio.sleep(random.uniform(1, 4)) 
        response = requests.post(f"{self.api_url}/chat/clearState/{os.environ.get('SESSION_NAME')}", json={"chatId": id}, headers=headers)
        response = requests.post(f"{self.api_url}/client/sendMessage/{os.environ.get('SESSION_NAME')}", json=payload, headers=headers)
        
        response = requests.post(f"{self.api_url}/client/sendPresenceUnAvailable/{os.environ.get('SESSION_NAME')}", json=payload, headers=headers)
        
        response.raise_for_status()
        print(f"[WhatsappService] '{message}' sent to {id}")
      except requests.RequestException as e:
          print(f"[WhatsappService] Failed to send message: {e}") 