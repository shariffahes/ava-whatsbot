from typing import Dict, Any, Optional
from buspal_backend.core.exceptions import ToolExecutionError
from buspal_backend.config.constants import TOOLS_MAP
from google.genai.types import GenerateContentConfig, Tool, GoogleSearch, UrlContext, Part
from buspal_backend.core.exceptions import AIServiceError
from buspal_backend.config.app_config import AIConfig
from google import genai
import inspect
import logging

from buspal_backend.types.ai_types import FunctionCall

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Handles execution of AI function calls."""
    
    def __init__(self):
        self.tools = TOOLS_MAP
    
    async def execute_function_call(self, function_call: FunctionCall, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a single function call and return the result."""
        try:
            if not function_call.name:
                raise ToolExecutionError("Function call name is required")
            
            function_name = function_call.name
            args = function_call.arguments if function_call.arguments else {}
            
            logger.info(f"Executing function: {function_name}")
            logger.info(f"Function arguments: {args}")
            
            # Static arguments to provide for some functions
            extra_args = self._get_extra_args(function_name, chat_id)
            
            # Handle special function executions
            if function_name == "search_google":
                return await self._handle_google_search(args)
            elif function_name == "send_reaction":
                return await self._handle_reaction(args)
            else:
                return await self._handle_standard_tool(function_name, args, extra_args)
                
        except Exception as e:
            logger.error(f"Tool execution failed for {function_call.name}: {e}")
            raise ToolExecutionError(f"Failed to execute {function_call.name}: {e}")
    
    def _get_extra_args(self, function_name: str, chat_id: Optional[str]) -> Dict[str, Any]:
        """Get additional arguments for specific functions."""
        if function_name in {"schedule_reminder", "get_scheduled_reminders", "add_expense", "calculate_expense_settlement", "get_expense_balance", "get_expense_history", "settle_payments", "switch_conversation_mode"} and chat_id:
            return {"chat_id": chat_id}
        return {}
    
    async def _handle_reaction(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reaction function call."""
        tool_func = self.tools.get("send_reaction")
        if not tool_func:
            raise ToolExecutionError("send_reaction tool not found")
        logger.info("send reaction logic started")
        result = await tool_func(**args)

        reactions = result.get('media', [])
        reaction_type = result.get('type')
        
        return {
            "reactions": reactions,
            "reaction_type": reaction_type,
            "contents": result.get('contents', []),
            "has_reactions": len(reactions) > 0
        }
    
    async def _handle_standard_tool(self, function_name: str, args: Dict[str, Any], extra_args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle standard tool execution."""
        tool_func = self.tools.get(function_name)
        if not tool_func:
            raise ToolExecutionError(f"Tool {function_name} not found")
        
        combined_args = {**args, **extra_args}
        
        if inspect.iscoroutinefunction(tool_func):
            result = await tool_func(**combined_args)
        else:
            result = tool_func(**combined_args)
        
        return {"result": result}
    
    async def _handle_google_search(self, args: Dict[str, Any]) -> dict[str, Any]:
        """Process query using Google's native tools."""
        try:
            query = args.get('query', None)
            if query is None:
                return {'error': 'Error occured searching google', 'success': False}
            google_search_tool = Tool(google_search=GoogleSearch())
            url_context_tool = Tool(url_context=UrlContext) # type: ignore
            
            config = GenerateContentConfig(
                system_instruction="Fulfill the user query using one of the tools defined to you.",
                tools=[google_search_tool, url_context_tool]
            )
            _ai_config = AIConfig(provider="gemini")
            client = genai.Client(api_key=_ai_config.api_key)
            response = await client.aio.models.generate_content(
                model=_ai_config.model_name,
                contents=[Part.from_text(text=query)],
                config=config
            )
            
            return {'result': response.text}
            
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process_with_native_tools: {e}")
            raise AIServiceError(f"Native tools processing failed: {e}") from e