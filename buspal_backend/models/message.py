from db.mongo import db
from datetime import datetime, timezone

class MessageModel:
    collection = db.messages

    @classmethod
    def save(cls, chat_id, user_id, chat_user_id, text, timestamp=None):
        cls.collection.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "chat_user_id": chat_user_id,
            "text": text,
            "timestamp": timestamp or datetime.now(timezone.utc)
        })

    @classmethod
    def get_recent(cls, chat_id, since_timestamp):
        return list(cls.collection.find({
            "chat_id": chat_id,
            "timestamp": {"$gte": since_timestamp}
        }).sort("timestamp", 1))