from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from buspal_backend.api import webhook
import httpx
import uvicorn
import os

# Initialize FastAPI app
app = FastAPI(
    title="BusPal Server",
    description="Your friendly bus guide",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ping-google")
async def ping_google():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("https://www.google.com")
            return {"status": "Internet OK", "code": response.status_code}
    except Exception as e:
        return {"status": "Internet Failed", "error": str(e)}

app.include_router(webhook.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info"
    )