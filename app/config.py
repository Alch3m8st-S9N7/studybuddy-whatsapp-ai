from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # WhatsApp API Conf
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str
    WHATSAPP_API_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_API_VERSION: str = "v20.0"
    
    # Hugging Face LLM Conf (Legacy)
    HF_API_KEY: Optional[str] = None
    HF_MODEL_ID: str = "mistralai/Mistral-7B-Instruct-v0.3"

    # Multi-LLM Conf
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None # Added support for xAI as Groq fallback

    # Optional DB Conf
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    
    # Optional Razorpay Conf
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
