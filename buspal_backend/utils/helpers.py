import requests
import os
import json
from typing import Any
from buspal_backend.models.user import UserModel
from buspal_backend.models.group import GroupModel
import re

base_url = os.getenv('WHATSAPP_API_URL')
session_name = os.getenv('SESSION_NAME')
headers = {
    "Content-Type": "application/json"
}
supported_media = ['image', 'sticker']

def fetch_messages(chat_id: str, n: int):
    try:
        data = {
            "chatId": chat_id,
            "searchOptions": {
                "limit": n
            }
        }
        result = requests.post(f"{base_url}/chat/fetchMessages/{session_name}", data=json.dumps(data), headers=headers)
        if result.status_code == 200:
          response = result.json()
          return response.get('messages')
    except Exception as e:
        print("Failed to fetch messages: ", e)

def download_media(chat_id: str, message_id: str):
      data = {
        "chatId": chat_id,
        "messageId": message_id
      }
      response = requests.post(f"{base_url}/message/downloadMedia/{session_name}", data=json.dumps(data), headers=headers)
      if response.status_code == 200:
         result = response.json()
         return {"mimeType": result['messageMedia']['mimetype'], "base64": result['messageMedia']['data']}
      return {}

def get_user_by(id: str, is_group: bool = False):
    try:
        res = None
        #Try to find it from db
        if is_group:
           res = GroupModel.get_by_id(id)
        else:
          res = UserModel.get_by_id(id)

        if res is not None:
           return res
      
        data = { "contactId": id }
        result = requests.post(f"{base_url}/contact/getClassInfo/{session_name}", data=json.dumps(data), headers=headers)
        if result.status_code == 200:
          response = result.json()
          contact_info = response.get('result')
          name = contact_info.get('name')
          res = None
          if is_group:
            res = GroupModel.create(id, name)
          else:
            res = UserModel.create(wa_id=id, name=name)
          return res
    except Exception as e:
        print("Failed to get contact: ", e)

def parse_wa_message(message: dict[str:Any], skip_media: bool = False, is_dm: bool = False):
    sender_id = message.get('author')
    if is_dm:
      if not message.get('id', {}).get('fromMe'):
        sender_id = message.get('from').get('_serialized')
    if sender_id is None:
        return {}
    if type(sender_id) != str:
        sender_id = sender_id.get('_serialized')

    media_content = {}
    wa_message = {"sender": sender_id}
    if skip_media == False and message.get('type') in supported_media:
        chat_id = message['id']['remote']
        message_id = message['id']['id']
        media_content = download_media(chat_id, message_id)
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