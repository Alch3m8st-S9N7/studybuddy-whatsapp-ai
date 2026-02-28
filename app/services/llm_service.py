import asyncio
import json
import os
from typing import List, Dict, Optional
import google.generativeai as genai
from groq import AsyncGroq
from app.config import settings
from app.utils.logger import logger
from app.prompts.templates import (
    BASE_SYSTEM_PROMPT, 
    MAP_PHASE_PROMPT, 
    REDUCE_PHASE_ALL_PROMPT,
    REDUCE_PHASE_SUMMARIZE_PROMPT,
    REDUCE_PHASE_EXAM_PROMPT,
    REDUCE_PHASE_RESUME_PROMPT,
    QUIZ_GENERATION_PROMPT,
    FLASHCARD_GENERATION_PROMPT,
    IMAGE_ANALYSIS_PROMPT,
    VOICE_ANALYSIS_PROMPT,
)


class LLMService:
    def __init__(self):
        # Initialize Gemini
        self.gemini_key = settings.GEMINI_API_KEY
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.gemini_model = None

        # Initialize Groq
        self.groq_key = settings.GROQ_API_KEY or settings.XAI_API_KEY
        self.is_xai = self.groq_key and self.groq_key.startswith("xai-")
        
        if self.groq_key:
            if self.is_xai:
                self.groq_client = AsyncGroq(api_key=self.groq_key, base_url="https://api.x.ai/v1")
            else:
                self.groq_client = AsyncGroq(api_key=self.groq_key)
        else:
            self.groq_client = None
        
        self.primary_provider = "gemini" if self.gemini_key else "groq" if self.groq_key else "none"

    # ==================== TEXT GENERATION ====================
    
    async def generate_gemini(self, prompt: str) -> str:
        """Generates text using Gemini 2.5 Flash."""
        if not self.gemini_model:
            raise ValueError("Gemini API key not configured.")
        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                f"{BASE_SYSTEM_PROMPT}\n\n{prompt}"
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}")
            raise e

    async def generate_groq(self, prompt: str, is_reduce: bool = False) -> str:
        """Generates text using Groq Llama 3 70B (or xAI Grok)."""
        if not self.groq_client:
            raise ValueError("API key not configured for Groq/xAI.")
        model_name = "grok-beta" if self.is_xai else "llama3-70b-8192"
        try:
            response = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": BASE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                model=model_name, 
                temperature=0.3,
                max_tokens=2000 if is_reduce else 800
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq/xAI API Error: {str(e)}")
            raise e
    # ==================== FREE-FORM CHAT (ChatGPT-like) ====================
    
    async def chat_with_memory(self, user_message: str, chat_history: list, language: str = "English") -> str:
        """Conversational AI with memory - makes the bot feel like ChatGPT."""
        if not self.gemini_model:
            return "❌ Chat requires Gemini API. Please configure GEMINI_API_KEY."
        
        try:
            # Build conversation context
            system = f"""{BASE_SYSTEM_PROMPT}

You are chatting on WhatsApp. Keep responses concise but helpful (under 500 words unless the user asks for detail).
Use WhatsApp formatting: *bold*, _italic_, ~strikethrough~, ```code```.
Use emojis naturally. Be friendly and conversational.
Respond in {language} unless the user writes in another language (then match their language).
If the user asks you to do something you can't (like browse the internet), suggest they paste the URL directly."""
            
            # Build the conversation string
            conversation = system + "\n\n"
            for msg in chat_history[-10:]:  # Last 10 messages for context
                role = "User" if msg["role"] == "user" else "Assistant"
                conversation += f"{role}: {msg['content']}\n"
            conversation += f"User: {user_message}\nAssistant:"
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                conversation
            )
            return response.text
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return f"❌ Sorry, I had trouble with that: {str(e)}"

    async def summarize_url(self, url: str, language: str = "English") -> str:
        """Fetches and summarizes web page content via Gemini."""
        if not self.gemini_model:
            return "❌ URL summarization requires Gemini API."
        
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15.0, follow_redirects=True,
                                       headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                
                # Get raw text (strip HTML tags simply)
                import re
                html = resp.text
                # Remove script/style blocks
                html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', html)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Truncate to ~15000 chars to avoid token limits
                text = text[:15000]
                
                if len(text) < 50:
                    return "❌ Couldn't extract meaningful content from that URL."
            
            prompt = f"""Summarize this webpage content. Respond in {language}.

URL: {url}

Content:
{text}

Provide:
🔗 *PAGE SUMMARY*
[3-5 sentence overview of the page]

🎯 *KEY POINTS*
[Bulleted list of the most important takeaways]
"""
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                f"{BASE_SYSTEM_PROMPT}\n\n{prompt}"
            )
            return response.text
        except httpx.HTTPStatusError:
            return "❌ Couldn't access that URL. It may be blocked or require login."
        except Exception as e:
            logger.error(f"URL summarize error: {str(e)}")
            return f"❌ Error summarizing URL: {str(e)}"

    # ==================== MULTIMODAL (Gemini Only) ====================
    
    async def analyze_image(self, image_path: str, language: str = "English") -> str:
        """Uses Gemini's vision to analyze an image (notes, whiteboard, diagram)."""
        if not self.gemini_model:
            return "❌ Image analysis requires Gemini API. Please configure GEMINI_API_KEY."
        
        try:
            # Upload the image file to Gemini
            image_file = await asyncio.to_thread(
                genai.upload_file, image_path
            )
            
            prompt = IMAGE_ANALYSIS_PROMPT.format(language=language)
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                [f"{BASE_SYSTEM_PROMPT}\n\n{prompt}", image_file]
            )
            
            # Clean up uploaded file
            try:
                await asyncio.to_thread(genai.delete_file, image_file)
            except Exception:
                pass
            
            return response.text
        except Exception as e:
            logger.error(f"Image analysis error: {str(e)}")
            return f"❌ Error analyzing image: {str(e)}"

    async def transcribe_audio(self, audio_path: str, language: str = "English") -> str:
        """Uses Gemini's multimodal API to transcribe and summarize audio."""
        if not self.gemini_model:
            return "❌ Audio transcription requires Gemini API. Please configure GEMINI_API_KEY."
        
        try:
            # Upload the audio file
            audio_file = await asyncio.to_thread(
                genai.upload_file, audio_path
            )
            
            # Wait for file to be processed
            while audio_file.state.name == "PROCESSING":
                await asyncio.sleep(1)
                audio_file = await asyncio.to_thread(genai.get_file, audio_file.name)
            
            prompt = f"""{BASE_SYSTEM_PROMPT}

Transcribe this audio recording accurately, then provide:

🎙️ *TRANSCRIPTION*
[Full transcription of the audio]

🎯 *KEY POINTS*  
[Bulleted list of important points]

📝 *STUDY NOTES*
[Organized notes ready for revision]

Respond in {language}."""
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                [prompt, audio_file]
            )
            
            # Clean up
            try:
                await asyncio.to_thread(genai.delete_file, audio_file)
            except Exception:
                pass
            
            return response.text
        except Exception as e:
            logger.error(f"Audio transcription error: {str(e)}")
            return f"❌ Error transcribing audio: {str(e)}"

    # ==================== DOCUMENT PIPELINE ====================
    
    async def process_document_pipeline(self, chunks: List[str], task_type: str = "all", language: str = "English", provider: str = None) -> str:
        """Runs the LLM pipeline with the best available provider."""
        if not chunks:
            return "No text could be extracted from the document."

        active_provider = provider if provider else self.primary_provider
        
        if active_provider == "none":
            return "❌ No API keys configured. Please add GEMINI_API_KEY or GROQ_API_KEY to your .env file."

        # --- GEMINI PIPELINE (NO CHUNKING) ---
        if active_provider == "gemini":
            logger.info("Using Gemini 2.5 - Bypassing map-reduce.")
            full_text = "\n\n".join(chunks)
            prompt = self._get_reduce_prompt(task_type, full_text, language)
                
            try:
                return await self.generate_gemini(prompt)
            except Exception as e:
                logger.error(f"Gemini failed: {str(e)}. Falling back to Groq if available.")
                if self.groq_client:
                    active_provider = "groq"
                else:
                    return f"❌ Gemini API Error: {str(e)}"

        # --- GROQ PIPELINE (MAP-REDUCE) ---
        if active_provider == "groq":
            engine_name = "xAI Grok" if self.is_xai else "Groq Llama 3"
            logger.info(f"Using {engine_name} for {len(chunks)} chunks.")
            
            sem = asyncio.Semaphore(5)
            async def map_chunk(i, chunk):
                async with sem:
                    prompt = MAP_PHASE_PROMPT.format(chunk=chunk)
                    try:
                        summary = await self.generate_groq(prompt)
                        return f"Section {i+1}:\n{summary}"
                    except:
                        return "Error summarizing this portion."
            
            tasks = [map_chunk(i, c) for i, c in enumerate(chunks)]
            summaries = await asyncio.gather(*tasks)
            combined = "\n\n".join(summaries)
            
            reduce_prompt = self._get_reduce_prompt(task_type, combined, language)
            try:
                return await self.generate_groq(reduce_prompt, is_reduce=True)
            except Exception as e:
                return f"❌ {engine_name} Error: {str(e)}"

    def _get_reduce_prompt(self, task_type: str, text: str, language: str) -> str:
        """Returns the appropriate reduce prompt for the task type."""
        prompts = {
            "summarize": REDUCE_PHASE_SUMMARIZE_PROMPT,
            "exam": REDUCE_PHASE_EXAM_PROMPT,
            "resume": REDUCE_PHASE_RESUME_PROMPT,
        }
        template = prompts.get(task_type, REDUCE_PHASE_ALL_PROMPT)
        return template.format(combined_summaries=text, language=language)

    # ==================== QUIZ GENERATION ====================
    
    async def generate_quiz(self, chunks: List[str], language: str = "English") -> List[Dict]:
        """Generates structured MCQ quiz questions as JSON."""
        full_text = "\n\n".join(chunks)
        prompt = QUIZ_GENERATION_PROMPT.format(combined_summaries=full_text, language=language)
        
        try:
            raw = await self.generate_gemini(prompt)
            # Clean the response - strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]  # Remove first line
                raw = raw.rsplit("```", 1)[0]  # Remove last fence
            
            questions = json.loads(raw)
            
            if isinstance(questions, list) and len(questions) > 0:
                return questions[:5]  # Cap at 5
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Quiz JSON parse error: {str(e)}\nRaw: {raw[:500]}")
            return []
        except Exception as e:
            logger.error(f"Quiz generation error: {str(e)}")
            return []

    # ==================== FLASHCARD GENERATION ====================
    
    async def generate_flashcards(self, chunks: List[str], language: str = "English") -> List[Dict]:
        """Generates structured flashcards as JSON."""
        full_text = "\n\n".join(chunks)
        prompt = FLASHCARD_GENERATION_PROMPT.format(combined_summaries=full_text, language=language)
        
        try:
            raw = await self.generate_gemini(prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            
            cards = json.loads(raw)
            
            if isinstance(cards, list) and len(cards) > 0:
                return cards[:7]  # Cap at 7
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Flashcard JSON parse error: {str(e)}\nRaw: {raw[:500]}")
            return []
        except Exception as e:
            logger.error(f"Flashcard generation error: {str(e)}")
            return []


llm_service = LLMService()
