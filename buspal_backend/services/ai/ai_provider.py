from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import json
import os
import logging
import importlib.util
from buspal_backend.config.app_config import AIConfig

logger = logging.getLogger(__name__)
class AIProvider(ABC):
    
    def __init__(self, config):
        self.config: AIConfig = config
        self._prompts, self._schemas = self._load_prompts_and_schemas()
        self._custom_tools = self._load_tools_config()

    def _load_tools_config(self) -> List[Dict[str, Any]]:
        """Load tools configuration once at startup."""
        try:
            with open(self.config.tools_config_path, 'r') as file:
                tools = json.load(file)
            logger.info(f"Loaded {len(tools)} custom tools")
            return tools
        except Exception as e:
            logger.error(f"Failed to load tools config: {e}")
            return []
    
    def _load_prompts_and_schemas(self) -> tuple[Dict[str, str], Dict[str, Any]]:
        """Load prompts and schemas from environment-specific constants file."""
        try:
            # Get the absolute path to the constants file
            constants_path = os.path.abspath(self.config.prompts_path)
            
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location("constants", constants_path)
            constants_module = importlib.util.module_from_spec(spec) # type: ignore
            spec.loader.exec_module(constants_module) # type: ignore
            
            prompts = constants_module.PROMPTS
            schemas = {}
            if hasattr(constants_module, 'SCHEMAS'):
                schemas = constants_module.SCHEMAS
            
            logger.info(f"Loaded {len(prompts)} prompts and {len(schemas)} schemas from {constants_path}")
            return prompts, schemas
            
        except Exception as e:
            logger.error(f"Failed to load prompts and schemas from {self.config.prompts_path}: {e}")
            return {}, {}

    @abstractmethod
    async def process(self, messages: List[Dict], additional_instructions: Optional[str] = None, 
                     chat_id: Optional[str] = None, override_instructions: Optional[str] = None, retry_count: int = 0) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def generate_completion(self, messages: List[Dict], key: str) -> str:
        """Generate simple completion message."""
        pass