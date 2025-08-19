from dataclasses import dataclass, field
from typing import List, Optional
import os
from dotenv import load_dotenv
from buspal_backend.types.enums import AIMode
load_dotenv()

@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 4
    backoff_factor: float = 2.0
    timeout_seconds: int = 30

@dataclass
class MessageConfig:
    """Configuration for message handling."""
    # Message count
    default_message_count: int = 1
    bot_reply_message_count: int = 30
    business_reply_message_count: int = 30
    
    # Trigger patterns
    bot_triggers: List[str] | str = field(default_factory=lambda: ["@bot", "bot", "ava"])
    group_suffix: str = "@g.us"
    
    # Thresholds
    bot_trigger_threshold: int = 75
    summary_message_threshold: int = 20
    
    # Media processing
    media_skip_threshold: int = 5

    def __post_init__(self):
       if os.environ.get("ENV") == "DEV":
          self.bot_triggers = "@localtest"
  

@dataclass
class AIConfig:
    """Configuration for AI service."""
    provider: Optional[str] = field(default=None)
    model_name: str = field(init=False)
    api_key: str = field(init=False)
    prompts_path: str = field(init=False)
    tools_config_path: str = field(init=False)
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    thinking_budget: int = 8000
    mode: AIMode = AIMode.BUDDY
    AI_PROVIDERS = {
        AIMode.BUDDY: "gemini"
    }

    def __post_init__(self):

        if not self.mode or self.mode not in self.AI_PROVIDERS:
          raise ValueError("mode variable is required")

        self.provider = self.provider or self.AI_PROVIDERS[self.mode]
        self.prompts_path = f"buspal_backend/environments/{self.mode.value}/constants.py"
        self.tools_config_path = f"buspal_backend/environments/{self.mode.value}/tools.json"
 
        if self.provider == "gemini":
          self.api_key = os.environ.get("GEMINI_API_KEY") # type: ignore
          self.model_name = "gemini-2.5-flash-preview-05-20"
        elif self.provider == "openai":
          self.api_key = os.environ.get("OPEN_AI_KEY") # type: ignore
          self.model_name = "gpt-4o-mini"
        
        if not self.api_key:
          raise ValueError("API_KEY environment variable is required")
        
@dataclass
class WhatsAppConfig:
    """Configuration for WhatsApp service."""
    api_url: str = field(init=False)
    def __post_init__(self):
        self.api_url = os.environ.get("WHATSAPP_API_URL") # type: ignore
        if self.api_url is None:
          raise ValueError("WHATSAPP_API_URL environment variable is required")

@dataclass
class AppConfig:
    """Main application configuration."""
    message_config: MessageConfig = field(default_factory=MessageConfig)
    ai_config: AIConfig = field(default_factory=AIConfig)
    whatsapp_config: WhatsAppConfig = field(default_factory=WhatsAppConfig)

# Global configuration instance
app_config = AppConfig()