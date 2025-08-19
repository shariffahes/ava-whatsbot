from typing import Optional
from buspal_backend.config.app_config import AIConfig
from buspal_backend.core.exceptions import AIServiceError
from buspal_backend.services.ai.agents_service import AgentService
from buspal_backend.types.enums import AIMode
from buspal_backend.services.ai.ai_provider import AIProvider
class AIServiceFactory:
  @staticmethod
  def get_service(mode: AIMode, forced_service: Optional[str] = None) -> AIProvider:
    from buspal_backend.services.ai.gemini_service import GeminiService
    
    provider = AIConfig.AI_PROVIDERS[mode]
    if provider == "gemini" or forced_service == "gemini":
      config = AIConfig(mode=mode, provider="gemini")
      return GeminiService(config)
    elif provider == "openai" or forced_service == "openai":
      config = AIConfig(mode=mode, provider="openai")
      return AgentService(config)
    raise AIServiceError("No matching service provider")