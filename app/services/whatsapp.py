import httpx
from fastapi import HTTPException
from app.config import settings
from app.utils.logger import logger
from typing import Dict, Any, List, Optional
import os

class WhatsAppService:
    def __init__(self):
        self.api_token = settings.WHATSAPP_API_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = settings.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def verify_webhook(self, mode: str, token: str, challenge: int) -> int:
        """Verifies the webhook setup request from Meta."""
        if mode == "subscribe" and token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            logger.info("WhatsApp Webhook verified successfully!")
            return challenge
        else:
            logger.error("Failed to verify WhatsApp Webhook!")
            raise HTTPException(status_code=403, detail="Invalid verify token")

    async def send_message(self, to_phone_number: str, text: str) -> Dict[str, Any]:
        """Sends a text message back to the user, chunking if needed."""
        max_length = 4000
        
        async with httpx.AsyncClient() as client:
            if len(text) <= max_length:
                return await self._send_chunk(client, to_phone_number, text)
            
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            results = []
            for chunk in chunks:
                result = await self._send_chunk(client, to_phone_number, chunk)
                results.append(result)
            return results[-1] if results else {}

    async def _send_chunk(self, client: httpx.AsyncClient, to_phone_number: str, text_chunk: str) -> Dict[str, Any]:
        """Send a single chunk of text."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone_number,
            "type": "text",
            "text": {"body": text_chunk}
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/messages", 
                headers=self.headers, 
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Message sent to {to_phone_number}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API Error: {e.response.text}")
            return {"error": e.response.text}
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return {"error": str(e)}

    async def send_interactive_buttons(self, to_phone_number: str, text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
        """Sends an interactive button message (up to 3 buttons max)."""
        formatted_buttons = []
        for i, btn in enumerate(buttons):
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", f"btn_{i}"),
                    "title": btn.get("title", f"Button {i}")[:20]
                }
            })
            
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": text
                },
                "action": {
                    "buttons": formatted_buttons
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages", 
                    headers=self.headers, 
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Interactive buttons sent to {to_phone_number}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API Error sending buttons: {e.response.text}")
                return {"error": e.response.text}
            except Exception as e:
                logger.error(f"Error sending buttons: {str(e)}")
                return {"error": str(e)}

    async def send_interactive_list(self, to_phone_number: str, body_text: str, button_text: str, sections: List[Dict]) -> Dict[str, Any]:
        """Sends an interactive list message (supports up to 10 items per section).
        
        sections format: [{"title": "Section", "rows": [{"id": "row_1", "title": "Row 1", "description": "..."}]}]
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {
                    "button": button_text[:20],
                    "sections": sections
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Interactive list sent to {to_phone_number}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API Error sending list: {e.response.text}")
                return {"error": e.response.text}
            except Exception as e:
                logger.error(f"Error sending list: {str(e)}")
                return {"error": str(e)}

    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Marks a message as read (shows blue ticks to the user)."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                return response.json()
            except Exception:
                return {}

    async def send_reaction(self, to_phone_number: str, message_id: str, emoji: str) -> Dict[str, Any]:
        """Reacts to a user's message with an emoji (e.g. ⚡🧠✅📄)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone_number,
            "type": "reaction",
            "reaction": {
                "message_id": message_id,
                "emoji": emoji
            }
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                return response.json()
            except Exception:
                return {}

    async def download_media(self, media_id: str, download_dir: str = "downloads", extension: str = "pdf") -> Optional[str]:
        """Downloads any media file sent via WhatsApp (PDF, audio, image)."""
        os.makedirs(download_dir, exist_ok=True)
        
        media_url_endpoint = f"https://graph.facebook.com/{self.api_version}/{media_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                url_response = await client.get(media_url_endpoint, headers=self.headers, timeout=10.0)
                url_response.raise_for_status()
                media_data = url_response.json()
                
                download_url = media_data.get('url')
                
                if not download_url:
                    logger.error(f"Could not get download URL for media_id {media_id}")
                    return None
                
                file_response = await client.get(download_url, headers=self.headers, timeout=30.0)
                file_response.raise_for_status()
                
                filepath = os.path.join(download_dir, f"{media_id}.{extension}")
                with open(filepath, "wb") as f:
                    f.write(file_response.content)
                    
                logger.info(f"Successfully downloaded media {media_id} to {filepath}")
                return filepath
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Error downloading media: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Exception downloading media: {str(e)}")
                return None

    async def download_audio(self, media_id: str) -> Optional[str]:
        """Downloads a voice note (OGG format)."""
        return await self.download_media(media_id, extension="ogg")

    async def download_image(self, media_id: str) -> Optional[str]:
        """Downloads an image file."""
        return await self.download_media(media_id, extension="jpg")

whatsapp_service = WhatsAppService()
