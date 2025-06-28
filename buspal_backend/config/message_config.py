from dataclasses import dataclass
from typing import List
import os
from dotenv import load_dotenv

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
    bot_reply_message_count: int = 20
    business_reply_message_count: int = 30
    
    # Trigger patterns
    bot_triggers: List[str] = None
    business_trigger: str = "@business"
    group_suffix: str = "@g.us"
    
    # Thresholds
    bot_trigger_threshold: int = 75
    summary_message_threshold: int = 20
    
    # Media processing
    media_skip_threshold: int = 5
    
    def __post_init__(self):
        if self.bot_triggers is None:
            #["@bot", "@Bot", "@BOT", "ava", "Ava"]
            self.bot_triggers = ["@secret70"]

@dataclass
class AIConfig:
    """Configuration for AI service."""
    model_name: str = "gemini-2.5-flash-preview-05-20"
    retry_config: RetryConfig = None
    thinking_budget: int = 8000
    api_key: str = None
    tools_config_path: str = "buspal_backend/config/tools.json"
    
    def __post_init__(self):
        if self.retry_config is None:
            self.retry_config = RetryConfig()
        if self.api_key is None:
            self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

@dataclass
class WhatsAppConfig:
    """Configuration for WhatsApp service."""
    api_url: str = None
    
    def __post_init__(self):
        if self.api_url is None:
            self.api_url = os.environ.get("WHATSAPP_API_URL")

@dataclass
class AppConfig:
    """Main application configuration."""
    message_config: MessageConfig = None
    ai_config: AIConfig = None
    whatsapp_config: WhatsAppConfig = None
    
    def __post_init__(self):
        if self.message_config is None:
            self.message_config = MessageConfig()
        if self.ai_config is None:
            self.ai_config = AIConfig()
        if self.whatsapp_config is None:
            self.whatsapp_config = WhatsAppConfig()

# Global configuration instance
app_config = AppConfig()