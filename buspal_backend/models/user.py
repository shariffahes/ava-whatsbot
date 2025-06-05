from db.mongo import db
from datetime import datetime, timezone

class UserModel:
    collection = db.users

    @classmethod
    def create(cls, user_id, name, phone=None, preferences=None):
        user = {
            "user_id": user_id,
            "name": name,
            "phone": phone,
            "created_at": datetime.now(timezone.utc),
            "preferences": preferences or {}, 
        }
        cls.collection.insert_one(user)

    @classmethod
    def get_by_id(cls, user_id):
        return cls.collection.find_one({"user_id": user_id})
