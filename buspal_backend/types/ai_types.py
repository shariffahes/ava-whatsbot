from typing import Any, List
from attr import dataclass


@dataclass
class CompletionResponse:
    text: str | None
    function_calls: List['FunctionCall']
    raw_response: Any

@dataclass
class FunctionCall:
    name: str | None
    arguments: dict | None

@dataclass
class AIContext:
    additional_instructions: str | None
    instructions: str
    chat_id: str | None
    metaData: dict[str, Any]