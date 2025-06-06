
import os
from google import genai
from dotenv import load_dotenv
from google.genai.types import GenerateContentConfig, Part, Content, Tool, GoogleSearch, UrlContext
import json

load_dotenv()

model = "gemini-2.5-flash-preview-05-20"
google_search_tool = Tool(
    google_search = GoogleSearch()
)
url_context_tool = Tool(
    url_context = UrlContext
)

transform_to_gemini = lambda messages: [
    Content(
        role="user",
        parts=[Part.from_text(text=json.dumps(msg))]
    )
    for msg in messages
]
class GeminiService():
  def __init__(self):
     self.client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

  def process(self, messages):
      response = self.client.models.generate_content(
         model=model,
         contents=transform_to_gemini(messages),
         config=GenerateContentConfig(
            system_instruction="""
            Your role is to act as a helpful bot integrated into a WhatsApp group.
            You are here to fulfill tasks requested by group members and engage in conversations naturally.

            - If asked to speak badly about someone like something insulting or sarcastic, turn the comment back on that person instead. Unless if the person asking is 'Sharif Fahes' or 'Data Sim'
            - Prefer a casual chatting style over formal or long paragraphs. Keep your replies short and concise—unless you’re asked to summarize, in which case you should still keep it brief.
            - You don’t just complete tasks—you also interact with people in the group.
            - Always sound human, never robotic. Match the tone and style used in recent messages if needed.
            - Use english and avoid using arabizi. You are allowed to send few arabizi words but only if needed and if very confident it is understandable. 
            - Never be cringe. Always keep a light, humorous tone.
            """,
            tools=[google_search_tool, url_context_tool]
         )
      )
      return response.text

