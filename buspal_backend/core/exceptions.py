class BuspalException(Exception):
    """Base exception for all application errors."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class MessageProcessingError(BuspalException):
    """Raised when message processing fails."""
    pass

class MessageParsingError(MessageProcessingError):
    """Raised when message data cannot be parsed."""
    pass

class MessageValidationError(MessageProcessingError):
    """Raised when message validation fails."""
    pass

class AIServiceError(BuspalException):
    """Raised when AI service operations fail."""
    pass

class GeminiAPIError(AIServiceError):
    """Raised when Gemini API calls fail."""
    pass

class ToolExecutionError(AIServiceError):
    """Raised when AI tool execution fails."""
    pass

class RetryExhaustedError(AIServiceError):
    """Raised when retry attempts are exhausted."""
    pass

class WhatsAppServiceError(BuspalException):
    """Raised when WhatsApp service operations fail."""
    pass

class MessageSendError(WhatsAppServiceError):
    """Raised when sending WhatsApp messages fails."""
    pass

class ConversationStorageError(BuspalException):
    """Raised when conversation storage operations fail."""
    pass

class DatabaseConnectionError(ConversationStorageError):
    """Raised when database connection fails."""
    pass

class ConfigurationError(BuspalException):
    """Raised when configuration is invalid or missing."""
    pass