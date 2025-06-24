from buspal_backend.db.mongo import db

class ConversationModel:
    collection = db.conversations

    @classmethod
    def create(cls, convo_id, name, messages=[], summaries=[]):
        conversation = {
            "convo_id": convo_id,
            "name": name,
            "messages": messages,
            "summaries": summaries,
        }
        cls.collection.insert_one(conversation)
        return conversation

    @classmethod
    def get_by_id(cls, id):
        return cls.collection.find_one({"convo_id": id})

    @classmethod
    def update_by_id(cls, convo_id, update_fields: dict, type: str = "$set"):
      result = cls.collection.update_one(
          {"convo_id": convo_id},
          {type: update_fields}
      )
      return result