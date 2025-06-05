from buspal_backend.db.mongo import db
from datetime import datetime, timezone

class UserModel:
    collection = db.users

    @classmethod
    def create(cls, wa_id, name, phone=None, preferences=None, last_read=None):
        user = {
            "wa_id": wa_id,
            "name": name,
            "phone": phone,
            "created_at": datetime.now(timezone.utc),
            "preferences": preferences or {},
            "last_read": last_read or {} #{<chat-id>: <last-read>}
        }
        cls.collection.insert_one(user)
        return user

    @classmethod
    def get_by_id(cls, user_id):
        return cls.collection.find_one({"wa_id": user_id})
