"""
Security utilities for the WhatsApp AI Bot.
Handles: webhook verification, input sanitization, phone masking, and data protection.
"""
import hashlib
import hmac
from typing import Optional
from app.config import settings
from app.utils.logger import logger


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verifies that a webhook request genuinely comes from Meta.
    
    Meta signs every webhook with HMAC-SHA256 using your App Secret.
    If WHATSAPP_APP_SECRET is not set, skip verification (dev mode).
    """
    app_secret = settings.WHATSAPP_APP_SECRET
    if not app_secret:
        return True  # Skip in dev mode
    
    try:
        # Meta sends: "sha256=<hex_digest>"
        if not signature.startswith("sha256="):
            return False
        
        expected_sig = signature.replace("sha256=", "")
        computed_sig = hmac.new(
            app_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_sig, expected_sig)
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


def mask_phone(phone: str) -> str:
    """Masks a phone number for safe logging. 
    Example: 919876543210 → 91****3210
    """
    if len(phone) <= 6:
        return "****"
    return phone[:2] + "****" + phone[-4:]


def sanitize_text(text: str, max_length: int = None) -> str:
    """Sanitizes user text input.
    - Strips leading/trailing whitespace
    - Enforces max length
    - Removes null bytes
    """
    if not text:
        return ""
    
    max_len = max_length or settings.MAX_MESSAGE_LENGTH
    
    # Remove null bytes (security risk)
    text = text.replace("\x00", "")
    
    # Strip whitespace
    text = text.strip()
    
    # Enforce max length
    if len(text) > max_len:
        text = text[:max_len] + "..."
    
    return text


def safe_log(message: str, phone: str = None) -> None:
    """Logs a message with masked phone number."""
    if phone:
        masked = mask_phone(phone)
        logger.info(f"[{masked}] {message}")
    else:
        logger.info(message)
