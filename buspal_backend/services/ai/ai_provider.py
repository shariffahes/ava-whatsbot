from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

class AIProvider(ABC):
    @abstractmethod
    async def process(self, messages: List[Dict], additional_instructions: Optional[str] = None, 
                     chat_id: Optional[str] = None, override_instructions: Optional[str] = None, retry_count: int = 0) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def generate_completion(self, messages: List[Dict], key: str) -> str:
        """Generate simple completion message."""
        pass
    
    @abstractmethod
    def _load_tools_config(self) -> List[Dict[str, Any]]:
        "load tools config from file based on environment mode"
        pass
    
    @abstractmethod
    def _load_prompts_and_schemas(self) -> tuple[Dict[str, str], Dict[str, Any]]:
        "load prompts and schemas from file based on environment mode"
        pass