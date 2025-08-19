from typing import List, Dict, Any, Optional
from google import genai
from google.genai.types import GenerateContentConfig, Tool
from buspal_backend.services.ai.mcp.manager import mcp_manager
from buspal_backend.services.ai.ai_provider import AIProvider
from buspal_backend.services.ai.processors.response_processor import ResponseProcessor
from buspal_backend.config.app_config import AIConfig
from buspal_backend.types.enums import AIMode
from buspal_backend.core.exceptions import AIServiceError, GeminiAPIError
from buspal_backend.services.ai.tools.tool_response_adapter import GeminiAdapter
from buspal_backend.types.ai_types import CompletionResponse, FunctionCall
from buspal_backend.utils.helpers import current_time_in_beirut, parse_gemini_message
import logging

logger = logging.getLogger(__name__)

class GeminiService(AIProvider):
    def __init__(self, config: AIConfig = AIConfig(mode=AIMode.BUDDY)):
        try:
            super().__init__(config)
            self.client = genai.Client(api_key=self.config.api_key)
            self.model = self.config.model_name
          
            # Initialize helper components
            self.response_processor = ResponseProcessor(self.client, GeminiAdapter())

        except Exception as e:
            logger.error(f"Failed to initialize GeminiService: {e}")
            raise GeminiAPIError(f"Service initialization failed: {e}") from e
    
    async def process(self, messages: List[Dict], context: Optional[str] = None, 
                     chat_id: Optional[str] = None, instructions: Optional[str] = None, retry_count: int = 0) -> Dict[str, Any]:
        """Process conversation messages and return AI response."""
        try:
            instructions = instructions or self._prompts.get('MAIN', '')
            config = self._build_config(instructions, context)

            #exclude media if this is the second try
            gemini_messages = parse_gemini_message(messages, retry_count == 1)

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=gemini_messages,
                config=config
            )
            logger.info(f"Initial Gemini response received. Count {retry_count}")
            logger.info(f"Function calls detected: {len(response.function_calls if response.function_calls else [])}")
            
            # Process function calls if present
            if response.function_calls:
                custom_response = CompletionResponse(
                    text=response.text.strip() if response.text else None,
                    function_calls=[FunctionCall(name=func_call.name, arguments=func_call.args) for func_call in response.function_calls],
                    raw_response=response
                )

                return await self.response_processor.process_function_calls(
                    custom_response, gemini_messages, config, self.model, None, chat_id
                )
            
            return {"text": response.text.strip() if response.text else None, "media": None}
            
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process: {e}", extra={"chat_id": chat_id})
            error_message = str(e)
            #Gemini failed possibly becuase of media processing rate limit
            if "500" in error_message and retry_count == 0:
                logger.info("Processing Failed. Retry without media")
                return await self.process(messages, context, chat_id, instructions, 1)
            raise AIServiceError(f"Processing failed: {e}") from e
    
    async def generate_completion(self, messages: List[Dict], prompt_key: str) -> Optional[str]:
        """Process messages for summarization or memory extraction."""
        try:
            instructions=self._prompts.get(prompt_key,'')
            schema = self._schemas.get(prompt_key, None)
            if not instructions and not schema:
                raise AIServiceError(f"No instructions or schema found for key: {prompt_key}")
          
            config = GenerateContentConfig(
                system_instruction=instructions,
                response_mime_type="application/json",
                response_schema=schema
            )
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=parse_gemini_message(messages),
                config=config
            )
            
            return response.text
            
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process_messages: {e}")
            raise AIServiceError(f"Message processing failed: {e}") from e
    
    def _build_config(self, instructions: Optional[str], context: Optional[str]) -> GenerateContentConfig:
        """Build configuration for AI processing."""
        if instructions is None:
            instructions = self._prompts.get('MAIN', '')

        instructions += f"\n#Current Date:\n{current_time_in_beirut()}\n\n"
        
        if context:
            instructions += context

        tools = [mcp.session for mcp in mcp_manager.mcps]
        if self._custom_tools:
            tools.append(Tool(function_declarations=self._custom_tools)) # type: ignore
        
        return GenerateContentConfig(
            system_instruction=instructions,
            tools=tools
        )