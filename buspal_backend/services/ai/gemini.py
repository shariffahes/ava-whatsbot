
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import re

load_dotenv()

model = "gemini-2.5-flash-preview-05-20"

def is_group_message(msg):
    remote_id = msg["id"]["remote"]
    return remote_id.endswith("@g.us")

def clean_mention_from_body(body: str, mention_id: str) -> str:
    """Remove specific mention from body. If result is empty, return fallback."""
    if not body or not mention_id:
        return body
    
    cleaned_body = re.sub(r"@37430656774237\b", '', body).strip()

    # If the message is now empty or just whitespace, return fallback
    return cleaned_body if cleaned_body else "you were mentioned"

class GeminiService():
  def __init__(self):
     self.client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

  def process(self, payload):
    message_payload = payload.get('message', {}).get('_data')
    if message_payload:
      message_body = message_payload.get('body')
      meta = message_payload.get('id')
      mention_list = message_payload.get('mentionedJidList')
      message_body = clean_mention_from_body(message_body, "@37430656774237")
      if meta.get("fromMe") == False:
        if is_group_message(message_payload) and "37430656774237@lid" not in mention_list:
          print("Ignore self message")
          return {}
        print("Received", message_body, " from ", message_payload.get('notifyName'), " on channel ", meta.get("remote"))
        return {"text": self.generate_response(message_body), "id": meta.get("remote")}
      print("Ignore self message")
      return {}

  def generate_response(self, body):
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=body),
            ],
        ),
    ]
    response = self.client.models.generate_content(model=model, contents=contents)

    return response.text

