import requests
import os
import json
from typing import Any
from buspal_backend.models.user import UserModel
import re

base_url = os.getenv('WHATSAPP_API_URL')
session_name = os.getenv('SESSION_NAME')
headers = {
    "Content-Type": "application/json"
}

def fetch_messages(chat_id: str):
    try:
        data = {
            "chatId": chat_id,
            "searchOptions": {
                "limit": 15
            }
        }
        result = requests.post(f"{base_url}/chat/fetchMessages/{session_name}", data=json.dumps(data), headers=headers)
       
        if result.status_code == 200:
          response = result.json()
          return response.get('messages')
    except Exception as e:
        print("Failed to fetch messages: ", e)

def get_user_by(id: str):
    try:
        data = { "contactId": id }
        result = requests.post(f"{base_url}/contact/getClassInfo/{session_name}", data=json.dumps(data), headers=headers)
        if result.status_code == 200:
          response = result.json()
          contact_info = response.get('result')
          name = contact_info.get('name')
          user = UserModel.create(wa_id=id, name=name)
          return user
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