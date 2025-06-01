from pydantic import BaseModel
from typing import Any

class WebhookPayload(BaseModel):
    sessionId: str
    dataType: str
    data: Any
