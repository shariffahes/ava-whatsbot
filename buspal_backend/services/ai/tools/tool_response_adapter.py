from abc import ABC, abstractmethod
from typing import Any, List, Optional
from google.genai.types import Part, Content, GenerateContentConfigOrDict
from google.genai.client import Client
from buspal_backend.types.ai_types import CompletionResponse, FunctionCall

class ToolResponseAdapter(ABC):
  "Abstact base class for tool response submission"

  @abstractmethod
  def parse_tool_response(self, function_call: Any, function_result: dict, messages: List[Any]) -> List[Any]:
    """Parse the tool response and return a formatted message structure."""
    pass

  @abstractmethod
  async def submit_response(self, client: Any, nessages: List[Any], config: Optional[Any], model: Optional[str]) -> CompletionResponse:
    """Submit the tool response to the appropriate service."""
    pass

  @abstractmethod
  def prepare_messages(self, prev: Any, result: CompletionResponse) -> List[Any]:
    pass


class GeminiAdapter(ToolResponseAdapter):

  def parse_tool_response(self, function_call: Any, function_result: dict, messages: List[Any]) -> List[Any]:
    function_response_part = Part.from_function_response(
        name=function_call.name,
        response=function_result
    )
    messages.append(Content(role="user", parts=[function_response_part]))
    return messages

  def prepare_messages(self, prev: Any, result: CompletionResponse) -> List[Any]:
    contents = []
    contents.extend(prev)
    contents.append(result.raw_response.candidates[0].content)
    return contents
  
  async def submit_response(self, client: Client, messages: List[Any], config: GenerateContentConfigOrDict, model: str) -> CompletionResponse:
      """Submit the tool response to Gemini."""
      try:
        response = await client.aio.models.generate_content(
              model=model,
              config=config,
              contents=messages
          )
        custom_response = CompletionResponse(
              text=response.text.strip() if response.text else None,
              function_calls=[FunctionCall(name=func_call.name, arguments=func_call.args) for func_call in response.function_calls] if response.function_calls else [],
              raw_response=response
          )
        return custom_response
      except Exception as e:
          raise RuntimeError(f"Failed to submit response: {e}")