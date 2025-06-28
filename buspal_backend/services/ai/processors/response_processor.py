from typing import Dict, Any, List, Optional
from google.genai.types import Part, Content
from buspal_backend.config.constants import SCHEMAS, PROMPTS
from buspal_backend.services.ai.tools.tool_executor import ToolExecutor
from google.genai.types import GenerateContentConfig
from buspal_backend.utils.helpers import parse_gemini_message
from buspal_backend.config.message_config import app_config
import json
import random
import logging

logger = logging.getLogger(__name__)

class ResponseProcessor:
    """Handles AI response processing and function call management."""
    
    def __init__(self, gemini_client, tool_executor: ToolExecutor):
        self.client = gemini_client
        self.tool_executor = tool_executor
        self.model = app_config.ai_config.model_name
    
    async def process_function_calls(self, response, prev_messages: List[Content], config, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Process function calls and return final response."""
        output = response.text
        media = None
        retry_count = 0
        max_retries = 4
        
        while retry_count < max_retries and response.function_calls:
            try:
                retry_count += 1
                contents = self._prepare_contents(prev_messages, response)
                
                for function_call in response.function_calls:
                    function_result = await self.tool_executor.execute_function_call(function_call, chat_id)
                    
                    # Handle special reaction processing
                    if function_call.name == "send_reaction" and function_result.get("has_reactions"):
                        media, should_reply, selected_reaction = await self._process_reaction_selection(
                            function_result, prev_messages
                        )
                        if not should_reply:
                            return {"text": None, "media": media}
                        function_result = {"gif_content": selected_reaction}
                    
                    # Add function response to contents
                    function_response_part = Part.from_function_response(
                        name=function_call.name,
                        response=function_result
                    )
                    contents.append(Content(role="user", parts=[function_response_part]))
                
                # Generate follow-up response
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    config=config,
                    contents=contents
                )
                output = response.text.strip() if response.text else None
                
            except (AttributeError, IndexError, TypeError) as e:
                logger.warning(f"Function call processing failed (attempt {retry_count}): {e}")
                output = "Sorry, I couldn't process your request."
                break
            except Exception as e:
                logger.error(f"Unexpected error in function call processing: {e}")
                output = "Sorry, something went wrong while processing your request."
                break
        
        return {"text": output.strip() if output else None, "media": media}
    
    def _prepare_contents(self, prev_messages: List[Content], response) -> List[Content]:
        """Prepare contents list for function call processing."""
        contents = []
        contents.extend(prev_messages)
        contents.append(response.candidates[0].content)
        return contents
    
    async def _process_reaction_selection(self, function_result: Dict[str, Any], prev_messages: List[Content]) -> tuple[Optional[Dict[str, Any]], bool]:
        """Process reaction selection using AI."""        
        reactions = function_result["reactions"]
        reaction_type = function_result["reaction_type"]
        contents = function_result["contents"]
        
        # Prepare messages for reaction selection
        msgs = prev_messages[-3:] if len(prev_messages) >= 3 else prev_messages
        msgs.extend(parse_gemini_message(contents))

        # Configure reaction picker
        reaction_picker_config = GenerateContentConfig(
            system_instruction=PROMPTS['REACTION_CHOICE_MAKER'],
            response_mime_type="application/json",
            response_schema=SCHEMAS['REACTION_CHOICE_MAKER']
        )
        
        try:
            result = self.client.models.generate_content(
                config=reaction_picker_config,
                contents=msgs,
                model=self.model
            )
            json_res = json.loads(result.text)
            index = json_res.get('index')
            should_reply = json_res.get('reply', False)
            
            # Fallback to random selection
            if index is None and not should_reply:
                index = random.randint(0, len(reactions) - 1)
            
            media = None
            if index is not None and 0 <= index < len(reactions):
                media = {"url": reactions[index], "type": reaction_type}
            selected_reaction = contents[index].get('gif_content', '')
            return media, should_reply, selected_reaction
            
        except Exception as e:
            logger.error(f"Reaction selection failed: {e}")
            # Fallback to random selection
            index = random.randint(0, len(reactions) - 1)
            media = {"url": reactions[index], "type": reaction_type}
            return media, False