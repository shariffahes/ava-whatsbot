from fastapi import APIRouter, Header, HTTPException
from models.webhook_payload import WebhookPayload
from services.webhooks.message_handler import MessageHandler

router = APIRouter()

# Handler registry
handler_map = {"message": MessageHandler() }

@router.post("/webhook/incoming")
async def receive_webhook(payload: WebhookPayload, x_api_key: str = Header(None)):
    handler = handler_map.get(payload.dataType)
    
    if not handler:
        return {"status": "not handled"}
    
    await handler.handle(payload.sessionId, payload.data)
    return {"status": "processed"}
