from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from buspal_backend.api import webhook
from buspal_backend.api.webhook import handler_map
from buspal_backend.services.ai.mcp.manager import mcp_manager
import uvicorn
import os
import json

SERVER_VERSION = "1.0.1"

# Open and load the JSON file
with open('buspal_backend/config/mcp.json', 'r') as file:
    mcp_config = json.load(file)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server starting up...")
    await mcp_manager.connect_servers()
    yield
    print("Server shut down...")
    for handler in handler_map.values():
        await mcp_manager.cleanup()
        

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