from db.mongo import db
from datetime import datetime, timezone

class ChatModel:
    collection = db.chats

    @classmethod
    def create(cls, chat_id, chat_type, name=None, participants=None, additional_prompt=None):
        chat = {
            "chat_id": chat_id,
            "type": chat_type,  # "group" or "private"
            "name": name,
            "participants": participants or [],  # list of {user_id, chat_user_id, alias}
            "additional_prompt": additional_prompt,
            "created_at": datetime.now(timezone.utc)
        }
        cls.collection.insert_one(chat)

    @classmethod
    def get_by_id(cls, chat_id):
        return cls.collection.find_one({"chat_id": chat_id})

    @classmethod
    def update_participants(cls, chat_id, participants):
        cls.collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"participants": participants}}
        )

    @classmethod
    def resolve_user_alias(cls, chat_id, chat_user_id):
        chat = cls.get_by_id(chat_id)
        for p in chat.get("participants", []):
            if p["chat_user_id"] == chat_user_id:
                return p
        return None