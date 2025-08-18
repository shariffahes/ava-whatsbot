from buspal_backend.db.mongo import db
from datetime import datetime, timezone
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class ExpenseParticipant:
    user_id: str
    name: str
    share_amount: float
    paid_amount: float = 0.0

class ExpenseModel:
    collection = db.expenses
    
    @classmethod
    def create(cls, convo_id: str, description: str, total_amount: float, 
               payer_id: str, payer_name: str, participants: List[Dict], 
               expense_type: str = "equal"):
        expense = {
            "convo_id": convo_id,
            "description": description,
            "total_amount": total_amount,
            "payer_id": payer_id,
            "payer_name": payer_name,
            "participants": participants,
            "expense_type": expense_type,
            "created_at": datetime.now(timezone.utc),
            "is_settled": False
        }
        result = cls.collection.insert_one(expense)
        expense["_id"] = result.inserted_id
        return expense
    
    @classmethod
    def get_by_convo_id(cls, convo_id: str, include_settled: bool = False):
        query = {"convo_id": convo_id}
        if not include_settled:
            query["is_settled"] = False
        return list(cls.collection.find(query).sort("created_at", -1))
    
    @classmethod
    def get_by_id(cls, expense_id):
        from bson import ObjectId
        return cls.collection.find_one({"_id": ObjectId(expense_id)})
    
    @classmethod
    def mark_settled(cls, expense_id):
        from bson import ObjectId
        return cls.collection.update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": {"is_settled": True, "settled_at": datetime.now(timezone.utc)}}
        )
    
    @classmethod
    def delete_by_id(cls, expense_id):
        from bson import ObjectId
        return cls.collection.delete_one({"_id": ObjectId(expense_id)})