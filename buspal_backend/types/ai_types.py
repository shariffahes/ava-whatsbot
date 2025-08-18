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