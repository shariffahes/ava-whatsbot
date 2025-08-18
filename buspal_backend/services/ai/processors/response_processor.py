from typing import Dict, Any, List, Optional
from google.genai.types import Content
from buspal_backend.types.enums import AIMode
from buspal_backend.services.ai.tools.tool_executor import ToolExecutor
from google.genai.types import GenerateContentConfig
from buspal_backend.services.ai.tools.tool_response_adapter import ToolResponseAdapter
from buspal_backend.types.ai_types import CompletionResponse
from buspal_backend.utils.helpers import parse_gemini_message
from buspal_backend.config.app_config import AIConfig
from google import genai
import json
import random
import logging
import importlib.util

logger = logging.getLogger(__name__)

class ResponseProcessor:
    """Handles AI response processing and function call management."""
    
    def __init__(self, client, response_adapter: ToolResponseAdapter):
        self.client = client
        self.tool_executor = ToolExecutor()
        self.response_adapter = response_adapter
    
    async def process_function_calls(self, response: CompletionResponse, prev_messages: List[Content], config, model: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Process function calls and return final response."""
        output = response.text
        media = None
        retry_count = 0
        max_retries = 4
        logger.info(f"Processing function calls: {len(response.function_calls)} found")
        while retry_count < max_retries and response.function_calls:
            try:
                retry_count += 1
                contents = self.response_adapter.prepare_messages(prev_messages, response)
                
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
                    contents = self.response_adapter.parse_tool_response(function_call, function_result, contents)

                # Generate follow-up response
                response = await self.response_adapter.submit_response(self.client, contents, config, model)
                
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
    
    
    async def _process_reaction_selection(self, function_result: Dict[str, Any], prev_messages: List[Content]) -> tuple[Optional[Dict[str, Any]], bool, Any]:
        """Process reaction selection using AI."""        
        reactions = function_result["reactions"]
        reaction_type = function_result["reaction_type"]
        contents = function_result["contents"]
        
        # Prepare messages for reaction selection
        msgs = prev_messages[-3:] if len(prev_messages) >= 3 else prev_messages
        msgs.extend(parse_gemini_message(contents))

        _local_config = AIConfig(mode=AIMode.BUDDY, provider="gemini")
        spec = importlib.util.spec_from_file_location("constants", _local_config.prompts_path)
        constants_module = importlib.util.module_from_spec(spec) # type: ignore
        spec.loader.exec_module(constants_module) # type: ignore
        prompts = constants_module.PROMPTS
        schemas = constants_module.SCHEMAS
               
        # Configure reaction picker
        reaction_picker_config = GenerateContentConfig(
            system_instruction=prompts['REACTION_CHOICE_MAKER'],
            response_mime_type="application/json",
            response_schema=schemas['REACTION_CHOICE_MAKER']
        )
        
        client = genai.Client(api_key=_local_config.api_key)
        try:
            result = client.models.generate_content(
                config=reaction_picker_config,
                contents=msgs,
                model=_local_config.model_name
            )
            json_res = json.loads(result.text) if result.text else {}
            index = json_res.get('index', None)
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
            return media, False, None