from db.mongo import db
from datetime import datetime, timezone

class SummaryModel:
    collection = db.summaries

    @classmethod
    def save(cls, chat_id, summary_text, from_ts, to_ts):
        cls.collection.insert_one({
            "chat_id": chat_id,
            "summary_text": summary_text,
            "from_timestamp": from_ts,
            "to_timestamp": to_ts,
            "created_at": datetime.now(timezone.utc)
        })

    @classmethod
    def get_latest(cls, chat_id):
        return cls.collection.find_one(
            {"chat_id": chat_id},
            sort=[("created_at", -1)]
        )