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

def parse_wa_message(message: dict[str:Any]):
    sender_id = message.get('author')
    if sender_id is None:
        return {}
    if type(sender_id) != str:
        sender_id = sender_id.get('_serialized')
    return {"sender": sender_id, "content": clean_mentions(message.get('body', ""))}


def clean_mentions(message: str) -> str:
    return re.sub(r"@\d+", "", message).strip()