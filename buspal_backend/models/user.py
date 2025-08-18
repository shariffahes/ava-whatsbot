from buspal_backend.db.mongo import db
from datetime import datetime, timezone

class UserModel:
    collection = db.users

    @classmethod
    def create(cls, wa_id, name, convo_id, phone=None, preferences=None, last_read=None):
        user = {
            "wa_id": wa_id,
            "convo_id": convo_id,
            "name": name,
            "phone": phone,
            "created_at": datetime.now(timezone.utc),
            "preferences": preferences or {},
            "last_read": last_read or {} #{<chat-id>: <last-read>}
        }
        cls.collection.insert_one(user)
        return user

    @classmethod
    def get_by_id(cls, user_id, convo_id):
        user = cls.collection.find_one({"wa_id": user_id})
        if user and not user.get("convo_id"):
            user["convo_id"] = convo_id
            cls.collection.update_one({"wa_id": user_id}, {"$set": {"convo_id": convo_id}})
            return user
        return user
            
    
    @classmethod
    def get_by_name(cls, name, convo_id):
        # First try exact match (case insensitive)
        user = cls.collection.find_one({
            "name": {"$regex": f"^{name}$", "$options": "i"},
            "convo_id": convo_id
        })
        
        # If no exact match, try prefix match with space separator (case insensitive)
        if not user:
            user = cls.collection.find_one({
                "name": {"$regex": f"^{name}($|\\s)", "$options": "i"},
                "convo_id": convo_id
            })
        
        return user
