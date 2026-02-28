from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import webhook
from app.config import settings

app = FastAPI(
    title="WhatsApp AI Bot API",
    description="Webhook server for Meta WhatsApp Cloud API powering an AI Assistant",
    version="1.0.0"
)

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "running", "environment": settings.ENVIRONMENT}
