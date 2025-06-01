from abc import ABC, abstractmethod

class WebhookHandler(ABC):
    @abstractmethod
    async def handle(self, session_id: str, data: dict):
        pass
