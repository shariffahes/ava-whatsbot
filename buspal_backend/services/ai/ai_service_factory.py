from buspal_backend.config.app_config import AIConfig
from buspal_backend.types.enums import AIMode
from buspal_backend.services.ai.ai_provider import AIProvider


class AIServiceFactory:
  @staticmethod
  def get_service(mode: AIMode) -> AIProvider:
    from buspal_backend.services.ai.gemini_service import GeminiService
    
    provider = AIConfig.AI_PROVIDERS[mode]

    if provider == "gemini":
      return GeminiService(mode=mode)
    return GeminiService(mode=mode) 