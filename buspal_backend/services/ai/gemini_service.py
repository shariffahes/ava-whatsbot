from typing import List, Dict, Any, Optional
from google import genai
from google.genai.types import GenerateContentConfig, Tool
from buspal_backend.services.ai.mcp.manager import mcp_manager
from buspal_backend.services.ai.tools.tool_executor import ToolExecutor
from buspal_backend.services.ai.processors.response_processor import ResponseProcessor
from buspal_backend.config.constants import PROMPTS, SCHEMAS
from buspal_backend.config.message_config import app_config
from buspal_backend.core.exceptions import AIServiceError, GeminiAPIError
from buspal_backend.utils.helpers import current_time_in_beirut, parse_gemini_message
import json
import logging

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            self.config = app_config.ai_config
            self.client = genai.Client(api_key=self.config.api_key)
            self.model = self.config.model_name
            
            # Initialize helper components
            self.tool_executor = ToolExecutor()
            self.response_processor = ResponseProcessor(self.client, self.tool_executor)
            
            # Load tools configuration once at startup
            self._custom_tools = self._load_tools_config()
            
        except Exception as e:
            logger.error(f"Failed to initialize GeminiService: {e}")
            raise GeminiAPIError(f"Service initialization failed: {e}") from e
    
    async def process(self, messages: List[Dict], context: Optional[str] = None, 
                     chat_id: Optional[str] = None, instructions: str = PROMPTS['BUDDY']) -> Dict[str, Any]:
        """Process conversation messages and return AI response."""
        try:
            config = self._build_config(instructions, context)
            gemini_messages = parse_gemini_message(messages)
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=gemini_messages,
                config=config
            )
            
            logger.info(f"Initial Gemini response received")
            logger.info(f"Function calls detected: {bool(response.function_calls)}")
            
            # Process function calls if present
            if response.function_calls:
                return await self.response_processor.process_function_calls(
                    response, gemini_messages, config, chat_id
                )
            
            return {"text": response.text.strip() if response.text else None, "media": None}
            
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process: {e}", extra={"chat_id": chat_id})
            raise AIServiceError(f"Processing failed: {e}") from e
    
    async def process_business(self, messages: List[Dict]) -> str:
        """Process business messages with structured output."""
        try:
            config = GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_budget=self.config.thinking_budget),
                response_mime_type="application/json",
                response_schema=SCHEMAS['BUSINESS'],
                system_instruction=PROMPTS['BUSINESS']
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
            logger.error(f"Unexpected error in process_business: {e}")
            raise AIServiceError(f"Business processing failed: {e}") from e
    
    async def process_messages(self, messages: List[Dict], is_memory: bool = False) -> str:
        """Process messages for summarization or memory extraction."""
        try:
            config_key = 'MEMORY_PROCESS' if is_memory else 'SUMMARY'
            
            config = GenerateContentConfig(
                system_instruction=PROMPTS[config_key],
                response_mime_type="application/json",
                response_schema=SCHEMAS[config_key]
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

    def _load_tools_config(self) -> Dict[str, Any]:
        """Load tools configuration once at startup."""
        try:
            with open(self.config.tools_config_path, 'r') as file:
                tools = json.load(file)
            logger.info(f"Loaded {len(tools)} custom tools")
            return tools
        except Exception as e:
            logger.error(f"Failed to load tools config: {e}")
            return []
    
    def _build_config(self, instructions: Optional[str], context: Optional[str]) -> GenerateContentConfig:
        """Build configuration for AI processing."""
        if instructions is None:
            instructions = PROMPTS['BUDDY']

        instructions += f"\n#Current Date:\n{current_time_in_beirut()}\n\n"
        
        if context:
            instructions += context

        tools = [mcp.session for mcp in mcp_manager.mcps]
        if self._custom_tools:
            tools.append(Tool(function_declarations=self._custom_tools))
        
        return GenerateContentConfig(
            system_instruction=instructions,
            tools=tools
        )