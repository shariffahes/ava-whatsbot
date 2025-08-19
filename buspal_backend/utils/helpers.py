from agents import FunctionTool, RunContextWrapper, Tool, TResponseInputItem
from buspal_backend.models.conversation import ConversationModel
from buspal_backend.models.user import UserModel
from typing import Any, List, Optional
from datetime import datetime
import re
import os
import pytz
import aiohttp
import logging

from buspal_backend.services.ai.processors.response_processor import ResponseProcessor
from buspal_backend.types.ai_types import AIContext, CompletionResponse, FunctionCall

logger = logging.getLogger(__name__)

base_url = os.getenv('WHATSAPP_API_URL')
session_name = os.getenv('SESSION_NAME')
supported_media = ['image', 'sticker', 'video']

# Global session for connection pooling
_global_session: Optional[aiohttp.ClientSession] = None

async def _get_http_session() -> aiohttp.ClientSession:
    """Get or create global aiohttp session with connection pooling"""
    global _global_session
    if _global_session is None or _global_session.closed:
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        _global_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
    return _global_session

async def cleanup_http_session():
    """Cleanup global session resources"""
    global _global_session
    if _global_session and not _global_session.closed:
        await _global_session.close()
        _global_session = None

async def fetch_messages(chat_id: str, n: int):
    try:
        data = {
            "chatId": chat_id,
            "searchOptions": {
                "limit": n
            }
        }
        session = await _get_http_session()
        async with session.post(f"{base_url}/chat/fetchMessages/{session_name}", json=data) as response:
            response.raise_for_status()
            result = await response.json()
            return result.get('messages')
    except aiohttp.ClientError as e:
        logger.error("Failed to fetch messages: ", e)
    except Exception as e:
        logger.error("Failed to fetch messages: ", e)

async def download_media(chat_id: str, message_id: str):
      try:
          data = {
            "chatId": chat_id,
            "messageId": message_id
          }
          session = await _get_http_session()
          async with session.post(f"{base_url}/message/downloadMedia/{session_name}", json=data) as response:
              response.raise_for_status()
              result = await response.json()
              return {"mimeType": result['messageMedia']['mimetype'], "base64": result['messageMedia']['data']}
      except aiohttp.ClientError as e:
          logger.error("Failed to download media: ", e)
          return {}
      except Exception as e:
          logger.error("Failed to download media: ", e)
          return {}

async def get_user_by(id: str, convo_id: str | None = None) -> Any:
    try:
        res = None
        #If convo id is none, then id is the convo id
        if convo_id is None:
           res = ConversationModel.get_by_id(id)
        else:
          res = UserModel.get_by_id(id, convo_id)

        if res is not None:
           return res
      
        data = { "contactId": id }
        session = await _get_http_session()
        async with session.post(f"{base_url}/contact/getClassInfo/{session_name}", json=data) as response:
            response.raise_for_status()
            result = await response.json()
            contact_info = result.get('result')
            name = contact_info.get('name')
            res = None
            if convo_id is None:
              res = ConversationModel.create(id, name)
            else:
              res = UserModel.create(wa_id=id, name=name, convo_id=convo_id)
            return res
    except aiohttp.ClientError as e:
        logger.error("Failed to get contact: ", e)
    except Exception as e:
        logger.error("Failed to get contact: ", e)

async def parse_wa_message(message: dict[str, Any], skip_media: bool = False, is_dm: bool = False):
    sender_id = message.get('author')
    if is_dm:
      if not message.get('id', {}).get('fromMe'):
        sender_id = message.get('from', {}).get('_serialized')
    if sender_id is None:
        return {}
    if type(sender_id) != str:
        sender_id = sender_id.get('_serialized')

    media_content = {}

    wa_message = {"sender": sender_id, "date": epoch_to_beirut(message.get('t', None))}
    if skip_media == False and message.get('type') in supported_media:
        chat_id = message['id']['remote']
        message_id = message['id']['id']
        media_content = await download_media(chat_id, message_id)
        wa_message = {**wa_message, **media_content}
        wa_message['message'] = message.get('caption', None)
    else:
       wa_message['message'] = clean_mentions(message.get('body', ""))
    wa_message['reply_to'] = message.get('quotedMsg', None)
    if message.get('quotedMsg'):
       msg = message['quotedMsg']
       is_media = msg['type'] in supported_media
       if is_media:
          wa_message['reply_to'] = None
       else:
          wa_message['reply_to']  = {"body": msg.get('body', None)}
    return wa_message

def clean_mentions(message: str) -> str:
    return re.sub(r"@\d+", "", message).strip()

def current_time_in_beirut():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    beirut = pytz.timezone("Asia/Beirut")
    beirut_now = utc_now.astimezone(beirut)
    return beirut_now


def epoch_to_beirut(epoch_timestamp, format_string='%Y-%m-%d %H:%M:%S %Z'):
    if epoch_timestamp is None:
        beirut_tz = pytz.timezone('Asia/Beirut')
        return datetime.now(beirut_tz).strftime(format_string)
    utc_dt = datetime.fromtimestamp(epoch_timestamp, tz=pytz.UTC)
    
    beirut_tz = pytz.timezone('Asia/Beirut')
    beirut_dt = utc_dt.astimezone(beirut_tz)
    
    return beirut_dt.strftime(format_string)

def parse_gemini_message(messages, exclude_media: bool = False):
    """Transform messages to Gemini format."""
    from google.genai.types import Content, Part
    import base64
    import json
    
    contents = []
    for msg in messages:
        parts = []
        media_content = None

        if "base64" in msg:
            media_content = msg
        elif msg.get("reply_to") and "base64" in msg["reply_to"]:
            media_content = msg["reply_to"]
        
        if media_content:
            if exclude_media:
                continue
            mime_type = media_content['mimeType']
            data = base64.b64decode(media_content['base64'])
            parts.append(Part.from_bytes(mime_type=mime_type, data=data))
            caption = msg.get("message", "")
            if caption:
                parts.append(Part.from_text(text=caption))
        else:
            parts.append(Part.from_text(text=json.dumps(msg)))
        
        if len(parts) > 0:       
            contents.append(Content(role="user", parts=parts))

    return contents

def parse_agent_messages(messages, exclude_media: bool = False) -> List[TResponseInputItem]:
    """Transform messages to OpenAI format."""
    import json
    msgs = []
    for message in messages:
      content = []
      media_content = None

      if "base64" in message:
          media_content = message
      elif message.get("reply_to") and "base64" in message["reply_to"]:
          media_content = message["reply_to"]
        
      if media_content:
          if exclude_media:
              continue
          mime_type = media_content['mimeType']
          data = media_content['base64']
          content.append({ "type": "input_image", "image_url": f"data:{mime_type};base64,{data}" })
          caption = message.get("message", "")
          if caption:
              content.append({"type": "input_text", "text": caption})
      else:
          content.append({"type": "input_text", "text": json.dumps(message)})
      
      if len(content) > 0:       
          msgs.append({"role": "user", "content": content})
    return msgs

def build_agent_tools(tools: List[dict[str, Any]]) -> List[Tool]:
    from buspal_backend.services.ai.processors.response_processor import ResponseProcessor

    func_tools = []
    processor = ResponseProcessor(None)

    for tool in tools:
        def make_invoke_tool(name, processor):
          return lambda *args, **kwargs: (
              run_function(name, processor, *args, **kwargs),
          )[-1]
        parameters = tool.get("parameters", {})
        parameters["additionalProperties"] = False
        func_tools.append(
            FunctionTool(
              name=tool['name'],
              description=tool['description'],
              params_json_schema=parameters,
              on_invoke_tool=make_invoke_tool(tool['name'], processor),
              strict_json_schema=False,
          )
        )
    return func_tools

async def run_function(function_name: str, processor: ResponseProcessor, ctx: RunContextWrapper[AIContext], kwargs: str) -> dict[str, Any]:
    import json
    args = json.loads(kwargs) if isinstance(kwargs, str) else kwargs or {}
    
    response = CompletionResponse(
        text=None,
        function_calls=[FunctionCall(
            name=function_name,
            arguments=args
        )],
        raw_response=None
    )
    chat_id = ctx.context.chat_id if ctx.context.chat_id else ""
    func_result =  await processor.process_function_calls(response, [], None, "", ctx, chat_id)
    return func_result
