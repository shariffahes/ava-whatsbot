
import aiohttp
import os
import asyncio
import random
from typing import Optional
import logging

logger = logging.getLogger(__name__)
SESSION_NAME = os.environ.get('SESSION_NAME')
class WhatsappService():
  def __init__(self, api_url: str):
      self.api_url = api_url
      self._session: Optional[aiohttp.ClientSession] = None
      self.timeout = aiohttp.ClientTimeout(total=30, connect=10)
  
  async def _get_session(self) -> aiohttp.ClientSession:
      """Get or create aiohttp session with connection pooling"""
      if self._session is None or self._session.closed:
          connector = aiohttp.TCPConnector(
              limit=100,  # Total connection pool size
              limit_per_host=30,  # Per-host connection pool size
              ttl_dns_cache=300,  # DNS cache TTL
              use_dns_cache=True,
          )
          self._session = aiohttp.ClientSession(
              connector=connector,
              timeout=self.timeout,
              headers={"Content-Type": "application/json"}
          )
      return self._session
      
  async def cleanup(self):
      """Cleanup session resources"""
      if self._session and not self._session.closed:
          await self._session.close()

  async def go_online_and_type(self, id: str):
      session = await self._get_session()
      payload = { "chatId": id }
      try:
          async with session.post(f"{self.api_url}/client/sendPresenceAvailable/{SESSION_NAME}", json=payload) as response:
              response.raise_for_status()
          async with session.post(f"{self.api_url}/chat/sendStateTyping/{SESSION_NAME}", json={"chatId": id}) as response:
              response.raise_for_status()
      except aiohttp.ClientError as e:
          logger.error(f"[WhatsappService] Failed to set online/typing status: {e}")

  async def stop_typing(self, id: str):
      session = await self._get_session()
      try:
          async with session.post(f"{self.api_url}/chat/clearState/{SESSION_NAME}", json={"chatId": id}) as response:
              response.raise_for_status()
      except aiohttp.ClientError as e:
          logger.error(f"[WhatsappService] Failed to stop typing: {e}")
  
  async def go_offline(self, id: str):
      session = await self._get_session()
      try:
          async with session.post(f"{self.api_url}/client/sendPresenceUnAvailable/{SESSION_NAME}", json={"chatId": id}) as response:
              response.raise_for_status()
      except aiohttp.ClientError as e:
          logger.error(f"[WhatsappService] Failed to go offline: {e}")
        
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
      
      session = await self._get_session()
      try:
        await self.stop_typing(id) 
        async with session.post(f"{self.api_url}/client/sendMessage/{SESSION_NAME}", json=payload) as response:
            response.raise_for_status()
            
        await asyncio.sleep(random.uniform(0.5, 1.5)) 
        await self.go_offline(id)
        
        logger.info(f"[WhatsappService] '{message}' sent to {id}")
      except aiohttp.ClientError as e:
          logger.error(f"[WhatsappService] Failed to send message: {e}") 