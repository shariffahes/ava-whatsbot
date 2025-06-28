from fastapi import APIRouter, Header
from buspal_backend.models.webhook_payload import WebhookPayload
from buspal_backend.services.webhooks.handlers.message_handler import MessageHandler
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Handler registry
handler_map = {"message": MessageHandler(), "message_create": MessageHandler() }

@router.post("/webhook/incoming")
async def receive_webhook(payload: WebhookPayload, x_api_key: str = Header(None)):
    handler = handler_map.get(payload.dataType)
    if not handler:
        return {"status": "not handled"}
    logger.info(f"Incoming Webhook {payload.dataType}")
    await handler.handle(payload.data, payload.dataType)
    return {"status": "processed"}
