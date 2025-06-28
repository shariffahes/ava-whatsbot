from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from buspal_backend.api import webhook
from buspal_backend.api.webhook import handler_map
from buspal_backend.services.ai.mcp.manager import mcp_manager
from buspal_backend.utils.helpers import cleanup_http_session
import uvicorn
import os
import json
import logging

logger = logging.getLogger(__name__)
SERVER_VERSION = "1.2.0"

# Open and load the JSON file
with open('buspal_backend/config/mcp.json', 'r') as file:
    mcp_config = json.load(file)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Server starting up...")
    await mcp_manager.connect_servers()
    yield
    logger.info("Server shutting down...")
    # Clean up resources
    await cleanup_http_session()
    for handler in handler_map.values():
        # Clean up WhatsApp service sessions if they exist
        if hasattr(handler, 'whatsapp_client') and hasattr(handler.whatsapp_client, 'cleanup'):
            await handler.whatsapp_client.cleanup()
    await mcp_manager.cleanup()
    logger.info("Server shut down complete.")
        

# Initialize FastAPI app
app = FastAPI(
    title="MyPal Server",
    description="Your friendly pal",
    version=SERVER_VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
@app.get("/")
async def root():
    return {
        "message": "Welcome to BusPal Server",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy :)",
        "timestamp": datetime.now().isoformat(),
        "version": SERVER_VERSION
    }

app.include_router(webhook.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info"
    )