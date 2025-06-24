
import os
from google import genai
from dotenv import load_dotenv
from google.genai.types import GenerateContentConfig, Part, Content, Tool, GoogleSearch, UrlContext
import json
import base64
import random
from buspal_backend.services.ai.mcp.manager import mcp_manager
from buspal_backend.config.constants import PROMPTS, TOOLS, SCHEMAS
import logging

logger = logging.getLogger(__name__)
with open('buspal_backend/config/tools.json', 'r') as file:
    custom_tools = json.load(file)

load_dotenv()

model = "gemini-2.5-flash-preview-05-20"

google_search_tool = Tool(
    google_search = GoogleSearch()
)
url_context_tool = Tool(
    url_context = UrlContext
)

VIDEO_PICKER_CONFIG = GenerateContentConfig(
  system_instruction=PROMPTS['REACTION_CHOICE_MAKER'],
  response_mime_type="application/json",
  response_schema=SCHEMAS['REACTION_CHOICE_MAKER']
)

MEMORY_CONFIG = GenerateContentConfig(
  system_instruction=PROMPTS['MEMORY_PROCESS'],
  response_mime_type="application/json",
  response_schema=SCHEMAS['MEMORY_PROCESS'],
)

SUMMARY_CONFIG = GenerateContentConfig(
  system_instruction=PROMPTS['SUMMARY'],
   response_mime_type="application/json",
  response_schema=SCHEMAS['SUMMARY']
)

BUSINESS_CONFIG = GenerateContentConfig(
  thinking_config = genai.types.ThinkingConfig(
      thinking_budget=8000,
  ),
  response_mime_type="application/json",
  response_schema=SCHEMAS['BUSINESS'],
  system_instruction=PROMPTS['BUSINESS']
)

def transform_to_gemini(messages):
    contents = []
    for msg in messages:
        parts = []
        media_content = None

        if "base64" in msg:
            media_content = msg
        elif msg.get("reply_to") and "base64" in msg["reply_to"]:
            media_content = msg["reply_to"]

        if media_content:
            mime_type = media_content['mimeType']
            data = base64.b64decode(media_content['base64'])
            parts.append(Part.from_bytes(mime_type=mime_type, data=data))
            caption = msg.get("message", "")
            if caption:
                parts.append(Part.from_text(text=caption))
        # elif "video" in msg:
        #     contents.append(Content(
        #         role="user",
        #         parts=[
        #             Part(
        #                 inline_data=Blob(data=msg['video'], mime_type='video/mp4')
        #             ),
        #             Part(text=f'index: {msg['index']}')
        #         ]
        #     ))
        else:
            parts.append(Part.from_text(text=json.dumps(msg)))
        
        if len(parts) > 0:       
          contents.append(Content(role="user", parts=parts))

    return contents
class GeminiService():
  def __init__(self):
      self.client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
      )

  async def process(self, messages, context = None, instructions=PROMPTS['BUDDY']):
      tools = [mcp.session for mcp in mcp_manager.mcps]
      tools.append(Tool(function_declarations=custom_tools))
      if context:
        instructions = instructions + context

      config = GenerateContentConfig(
          system_instruction=instructions,
          tools=tools
      )
        
      response = await self.client.aio.models.generate_content(
        model=model,
        contents=transform_to_gemini(messages),
        config=config
      )

      output = None
      media = None
      retry_count = 0
      while output is None and retry_count < 4:
          try:
              retry_count += 1
              function_call = response.candidates[0].content.parts[0].function_call
              contents = []
              function_call = response.candidates[0].content.parts[0].function_call
              logger.info(f"Function to call: {function_call.name}")
              logger.info(f"Arguments: {function_call.args}")
              should_reply = True
              if function_call.name == "search_google":
                  result = self.process_with_native_tools(**function_call.args)
              elif function_call.name == "send_reaction":
                  result = TOOLS[function_call.name](**function_call.args)
                  reactions = result.get('media', [])
                  reaction_type = result.get('type')
                  
                  if len(reactions) > 0:
                      msgs = messages[-3:]
                      msgs.extend(result.get('contents', []))
                      result = self.client.models.generate_content(
                          config=VIDEO_PICKER_CONFIG,
                          contents=transform_to_gemini(msgs),
                          model=model
                      )
                      logger.info(result.text)
                      json_res = json.loads(result.text)
                      index = json_res.get('index', None)
                      should_reply = json_res.get('reply', False)
                      if index is None and should_reply == False:
                          index = random.uniform(0, len(reactions) -1)
                      if index is not None:
                        media = { "url": reactions[index], "type": reaction_type }
                      result = {"gif_content": json_res.get('gif_content', "")}
              else:
                  result = TOOLS[function_call.name](**function_call.args)
              logger.info(result)
              if should_reply == False:
                  return {"media": media, "text": None}
              
              function_response_part = Part.from_function_response(
                  name=function_call.name,
                  response={"result": result},
              )

              contents.extend(transform_to_gemini(messages))
              contents.append(response.candidates[0].content)
              contents.append(Content(role="user", parts=[function_response_part]))
              response = await self.client.aio.models.generate_content(
                  model=model,
                  config=config,
                  contents=contents,
              )
              output = response.text.strip()
          except (AttributeError, IndexError, TypeError) as exp:
              function_call = None
              print("Exception Here: ", exp)
              output = response.text.strip() if response.text else "Sorry, I couldn't process your request."
          except Exception as e:
            print("Exception Raised ", e)
            output = "Sorry, something went wrong while processing your request."
            raise 

      return {"text": output, "media": media}
  
  def process_with_native_tools(self, query):
      config = GenerateContentConfig(
          system_instruction="Filfill the user query using one of the tools defined to you.",
          tools=[google_search_tool, url_context_tool]
        )
      response = self.client.models.generate_content(
        model=model,
        contents=[Part.from_text(text=query)],
        config=config,
      )
      return response.text

  def process_messages(self, messages, is_memory=None):
      config = SUMMARY_CONFIG
      if is_memory:
          config = MEMORY_CONFIG

      response = self.client.models.generate_content(
         model=model,
         contents=transform_to_gemini(messages),
         config=config
      )
      return response.text
  
  def process_business(self, messages):
      response = self.client.models.generate_content(
         model=model,
         contents=transform_to_gemini(messages),
         config=BUSINESS_CONFIG
      )
      return response.text

