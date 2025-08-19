import logging
from typing import Any, Dict, List
from buspal_backend.config.app_config import AIConfig
from buspal_backend.core.exceptions import AIServiceError
from buspal_backend.services.ai.ai_provider import AIProvider
from buspal_backend.types.ai_types import AIContext
from buspal_backend.types.enums import AIMode
from agents import Agent, RunContextWrapper, Runner, set_default_openai_key

from buspal_backend.utils.helpers import build_agent_tools, current_time_in_beirut, parse_agent_messages

logger = logging.getLogger(__name__)

def dynamic_instructions(
    context: RunContextWrapper[AIContext], agent: Agent[AIContext]
) -> str:
    instructions = context.context.instructions + f"\n#Current Date:\n{current_time_in_beirut()}\n\n"
    additional_instructions = context.context.additional_instructions
    if additional_instructions:
      instructions += additional_instructions
    
    return instructions


class AgentService(AIProvider):
    
    def __init__(self, config: AIConfig = AIConfig(mode=AIMode.BUDDY)):
        super().__init__(config)
        set_default_openai_key(self.config.api_key)
        self.agent = Agent(
            name=self.config.mode.value + "_agent",
            instructions=dynamic_instructions,
            model=self.config.model_name,
            tools=build_agent_tools(self._custom_tools)
          )

    async def process(self, messages: List[Dict], additional_instructions: str | None = None, chat_id: str | None = None, override_instructions: str | None = None, retry_count: int = 0) -> Dict[str, Any]:
        try:
          prompt = override_instructions if override_instructions else self._prompts.get('MAIN', '')
          context = AIContext(instructions=prompt, additional_instructions=additional_instructions, chat_id=chat_id, metaData={})

          formatted_messages = parse_agent_messages(messages, retry_count == 1)
          
          run = await Runner.run(self.agent, formatted_messages, context=context)
          
          output_text = run.final_output
          response_meta = run.context_wrapper.context.metaData or {}
          
          if response_meta.get('halt_reply'):
              output_text = None
              
          return {"text": output_text, "media": response_meta.get('media', None)}
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process: {e}", extra={"chat_id": chat_id})
            error_message = str(e)
            if "500" in error_message and retry_count == 0:
                logger.info("Processing Failed. Retry without media")
                return await self.process(messages, additional_instructions, chat_id, override_instructions, 1)
            raise AIServiceError(f"Processing failed: {e}") from e 
    
    async def generate_completion(self, messages: List[Dict], key: str) -> str:
        try:
            instructions=self._prompts.get(key,'')
            schema = self._schemas.get(key, None)
            if not instructions and not schema:
                raise AIServiceError(f"No instructions or schema found for key: {key}")
            
            agent = Agent(
                name="Completion",
                instructions=instructions,
                model=self.config.model_name
            )
            
            input = parse_agent_messages(messages)

            response = await Runner.run(agent, input)
            return response.final_output
        except AIServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in process_messages: {e}")
            raise AIServiceError(f"Message processing failed: {e}") from e
  