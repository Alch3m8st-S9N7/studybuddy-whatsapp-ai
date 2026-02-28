import re
import random
import asyncio
from fastapi import APIRouter, Request, BackgroundTasks, Response
from app.utils.logger import logger
from app.services.whatsapp import whatsapp_service
from app.services.pdf_processor import pdf_processor
from app.services.llm_service import llm_service
from app.utils.rate_limit import rate_limiter
from app.services.db_logger import db_logger
from app.services.session_manager import (
    session_manager, conversation_tracker, WELCOME_MESSAGE, HELP_MESSAGE, PROCESSING_MESSAGES
)

router = APIRouter()

# URL pattern for detecting links in messages
URL_PATTERN = re.compile(r'https?://[^\s]+')


@router.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp Cloud API Webhook Verification."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    result = whatsapp_service.verify_webhook(mode, token, int(challenge) if challenge else 0)
    return Response(content=str(result))


@router.post("/webhook")
async def handle_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming WhatsApp messages — the brain of the bot."""
    body = await request.json()
    logger.info("Incoming webhook")

    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" not in value:
            return {"status": "ok"}
        
        message = value["messages"][0]
        from_phone = message.get("from")
        message_type = message.get("type")
        message_id = message.get("id")

        # === RICH UX: Mark message as read (blue ticks) ===
        background_tasks.add_task(whatsapp_service.mark_as_read, message_id)

        # === MONTHLY USAGE LIMIT CHECK ===
        if not conversation_tracker.is_allowed(from_phone):
            background_tasks.add_task(
                whatsapp_service.send_message, from_phone,
                conversation_tracker.get_limit_message()
            )
            return {"status": "ok"}

        # === FIRST-TIME WELCOME ===
        if session_manager.is_first_visit(from_phone):
            background_tasks.add_task(whatsapp_service.send_message, from_phone, WELCOME_MESSAGE)
            # Show interactive buttons right after welcome
            background_tasks.add_task(
                whatsapp_service.send_interactive_buttons,
                from_phone,
                "👇 Tap a button below to explore:",
                [
                    {"id": "btn_features", "title": "✨ Features"},
                    {"id": "btn_help", "title": "❓ Help"},
                    {"id": "btn_menu", "title": "📋 Menu"},
                ]
            )
            if message_type == "text":
                return {"status": "ok"}

        # ========== ROUTE BY MESSAGE TYPE ==========
        if message_type == "document":
            background_tasks.add_task(whatsapp_service.send_reaction, from_phone, message_id, "📄")
            await handle_document(from_phone, message, background_tasks)

        elif message_type == "image":
            background_tasks.add_task(whatsapp_service.send_reaction, from_phone, message_id, "📸")
            await handle_image(from_phone, message, background_tasks)

        elif message_type == "audio":
            background_tasks.add_task(whatsapp_service.send_reaction, from_phone, message_id, "🎙️")
            await handle_audio(from_phone, message, background_tasks)

        elif message_type == "interactive":
            await handle_interactive(from_phone, message, background_tasks)

        elif message_type == "text":
            background_tasks.add_task(whatsapp_service.send_reaction, from_phone, message_id, "⚡")
            await handle_text(from_phone, message, background_tasks)

    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        
    return {"status": "ok"}


# ==================== DOCUMENT HANDLER ====================

async def handle_document(from_phone: str, message: dict, bg: BackgroundTasks):
    document = message.get("document", {})
    media_id = document.get("id")
    filename = document.get("filename", "document.pdf")
    mime_type = document.get("mime_type", "")
    
    if "pdf" not in mime_type.lower():
        bg.add_task(whatsapp_service.send_message, from_phone, 
                    "📄 I only process *PDF documents* right now. Please send a PDF file!")
        return

    if not rate_limiter.is_allowed(from_phone):
        bg.add_task(whatsapp_service.send_message, from_phone, 
                    "⏳ You've hit the limit (5 docs/hour). Take a break and come back soon! ☕")
        return
    
    session_manager.store_document(from_phone, media_id, filename)
    
    # Show language selection
    sections = [{
        "title": "🌍 Choose Language",
        "rows": [
            {"id": "lang_english", "title": "English", "description": "Respond in English"},
            {"id": "lang_hindi", "title": "हिंदी (Hindi)", "description": "हिंदी में जवाब दें"},
            {"id": "lang_spanish", "title": "Español (Spanish)", "description": "Responder en español"},
            {"id": "lang_french", "title": "Français (French)", "description": "Répondre en français"},
            {"id": "lang_german", "title": "Deutsch (German)", "description": "Auf Deutsch antworten"},
            {"id": "lang_chinese", "title": "中文 (Chinese)", "description": "用中文回答"},
            {"id": "lang_japanese", "title": "日本語 (Japanese)", "description": "日本語で回答"},
            {"id": "lang_arabic", "title": "العربية (Arabic)", "description": "الرد بالعربية"},
        ]
    }]
    
    bg.add_task(
        whatsapp_service.send_interactive_list,
        from_phone,
        f"📄 Received *{filename}*!\n\nFirst, choose the language for the AI response:",
        "Select Language",
        sections
    )


# ==================== IMAGE HANDLER ====================

async def handle_image(from_phone: str, message: dict, bg: BackgroundTasks):
    image = message.get("image", {})
    media_id = image.get("id")
    
    bg.add_task(whatsapp_service.send_message, from_phone, 
                "📸 Got your image! Analyzing with AI vision... 🔍")
    bg.add_task(process_image, from_phone, media_id)


async def process_image(from_phone: str, media_id: str):
    filepath = None
    try:
        filepath = await whatsapp_service.download_image(media_id)
        if not filepath:
            await whatsapp_service.send_message(from_phone, "❌ Couldn't download the image. Please try again!")
            return
        
        language = session_manager.get_language(from_phone)
        result = await llm_service.analyze_image(filepath, language=language)
        await whatsapp_service.send_message(from_phone, result)
        
        session_manager.record_activity(from_phone)
    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Error: {str(e)}")
    finally:
        if filepath:
            pdf_processor.delete_file(filepath)


# ==================== AUDIO HANDLER ====================

async def handle_audio(from_phone: str, message: dict, bg: BackgroundTasks):
    audio = message.get("audio", {})
    media_id = audio.get("id")
    
    bg.add_task(whatsapp_service.send_message, from_phone, 
                "🎙️ Got your voice note! Transcribing and analyzing... ✍️")
    bg.add_task(process_audio, from_phone, media_id)


async def process_audio(from_phone: str, media_id: str):
    filepath = None
    try:
        filepath = await whatsapp_service.download_audio(media_id)
        if not filepath:
            await whatsapp_service.send_message(from_phone, "❌ Couldn't download the voice note. Please try again!")
            return
        
        language = session_manager.get_language(from_phone)
        result = await llm_service.transcribe_audio(filepath, language=language)
        await whatsapp_service.send_message(from_phone, result)
        
        session_manager.record_activity(from_phone)
    except Exception as e:
        logger.error(f"Audio processing error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Error: {str(e)}")
    finally:
        if filepath:
            pdf_processor.delete_file(filepath)


# ==================== TEXT HANDLER (ChatGPT-like) ====================

async def handle_text(from_phone: str, message: dict, bg: BackgroundTasks):
    text = message.get("text", {}).get("body", "").strip()
    text_lower = text.lower()
    
    # --- SPECIAL COMMANDS ---
    if text_lower in ["hi", "hello", "hey", "start"]:
        bg.add_task(whatsapp_service.send_message, from_phone,
                    "👋 Hey there! I'm *StudyBuddy AI* — your personal AI assistant on WhatsApp! 🤖\n\n"
                    "Ask me anything, or tap below to explore:")
        bg.add_task(
            whatsapp_service.send_interactive_buttons,
            from_phone,
            "What would you like to do?",
            [
                {"id": "btn_features", "title": "✨ Features"},
                {"id": "btn_help", "title": "❓ Help"},
                {"id": "btn_menu", "title": "📋 Menu"},
            ]
        )
        return
    
    if text_lower in ["help",  "/help", "?"]:
        bg.add_task(whatsapp_service.send_message, from_phone, HELP_MESSAGE)
        return
    
    if text_lower in ["streak", "/streak"]:
        streak_msg = session_manager.get_streak_message(from_phone)
        bg.add_task(whatsapp_service.send_message, from_phone, streak_msg)
        return
    
    if text_lower in ["usage", "stats", "/usage"]:
        bg.add_task(whatsapp_service.send_message, from_phone,
                    conversation_tracker.get_usage_stats())
        return
    
    if text_lower in ["clear", "reset", "/clear"]:
        session_manager.clear_history(from_phone)
        bg.add_task(whatsapp_service.send_message, from_phone, 
                    "🧹 Chat memory cleared! Starting fresh. ✨")
        return
    
    if text_lower in ["menu", "/menu"]:
        bg.add_task(whatsapp_service.send_message, from_phone,
                    "🤖 *StudyBuddy AI — What can I do?*\n\n"
                    "💬 Ask me *anything* — I'm like ChatGPT!\n"
                    "📄 Send a *PDF* → Summarize, quiz, flashcards\n"
                    "📸 Send a *photo* → Read notes & whiteboards\n"
                    "🎙️ Send a *voice note* → Transcription + notes\n"
                    "🔗 Paste a *URL* → Summarize any article\n"
                    "💻 Ask about *code* → Debug & explain\n\n"
                    "⌨️ *Commands:* help | streak | clear | menu | lang")
        return
    
    if text_lower in ["lang", "language", "/lang"]:
        sections = [{
            "title": "🌍 Choose Language",
            "rows": [
                {"id": "langpref_english", "title": "English"},
                {"id": "langpref_hindi", "title": "हिंदी (Hindi)"},
                {"id": "langpref_spanish", "title": "Español (Spanish)"},
                {"id": "langpref_french", "title": "Français (French)"},
                {"id": "langpref_german", "title": "Deutsch (German)"},
                {"id": "langpref_chinese", "title": "中文 (Chinese)"},
                {"id": "langpref_japanese", "title": "日本語 (Japanese)"},
                {"id": "langpref_arabic", "title": "العربية (Arabic)"},
            ]
        }]
        bg.add_task(
            whatsapp_service.send_interactive_list,
            from_phone,
            "🌍 Choose your preferred response language:",
            "Select Language",
            sections
        )
        return
    
    # --- URL DETECTION ---
    urls = URL_PATTERN.findall(text)
    if urls:
        bg.add_task(whatsapp_service.send_message, from_phone, 
                    f"🔗 Detected a link! Fetching and summarizing... ✨")
        bg.add_task(process_url, from_phone, urls[0], text)
        return
    
    # --- FREE-FORM AI CHAT (The ChatGPT Experience) ---
    bg.add_task(process_chat, from_phone, text)


async def process_chat(from_phone: str, user_message: str):
    """Processes a free-form text message through Gemini with conversation memory."""
    try:
        # Get conversation history
        history = session_manager.get_history(from_phone)
        language = session_manager.get_language(from_phone)
        
        # Generate response with context
        response = await llm_service.chat_with_memory(user_message, history, language)
        
        # Store both messages in history
        session_manager.add_message(from_phone, "user", user_message)
        session_manager.add_message(from_phone, "assistant", response)
        
        # Send the response
        await whatsapp_service.send_message(from_phone, response)
        
        session_manager.record_activity(from_phone)
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Something went wrong: {str(e)}")


async def process_url(from_phone: str, url: str, original_text: str):
    """Fetches a URL and summarizes its content."""
    try:
        language = session_manager.get_language(from_phone)
        result = await llm_service.summarize_url(url, language)
        await whatsapp_service.send_message(from_phone, result)
        
        session_manager.add_message(from_phone, "user", f"Summarize: {url}")
        session_manager.add_message(from_phone, "assistant", result)
        session_manager.record_activity(from_phone)
        
    except Exception as e:
        logger.error(f"URL processing error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Error: {str(e)}")


# ==================== INTERACTIVE HANDLER ====================

async def handle_interactive(from_phone: str, message: dict, bg: BackgroundTasks):
    interactive = message.get("interactive", {})
    reply_type = interactive.get("type")
    
    if reply_type == "button_reply":
        button_id = interactive["button_reply"]["id"]
        await handle_button_reply(from_phone, button_id, bg)
    elif reply_type == "list_reply":
        list_id = interactive["list_reply"]["id"]
        await handle_list_reply(from_phone, list_id, bg)


async def handle_list_reply(from_phone: str, list_id: str, bg: BackgroundTasks):
    """Handles language selection from lists (both PDF-context and global preference)."""
    
    # Language map for both PDF flow (lang_*) and preference flow (langpref_*)
    lang_map = {
        "lang_english": "English", "langpref_english": "English",
        "lang_hindi": "Hindi", "langpref_hindi": "Hindi",
        "lang_spanish": "Spanish", "langpref_spanish": "Spanish",
        "lang_french": "French", "langpref_french": "French",
        "lang_german": "German", "langpref_german": "German",
        "lang_chinese": "Chinese", "langpref_chinese": "Chinese",
        "lang_japanese": "Japanese", "langpref_japanese": "Japanese",
        "lang_arabic": "Arabic", "langpref_arabic": "Arabic",
    }
    
    if list_id in lang_map:
        language = lang_map[list_id]
        session_manager.set_language(from_phone, language)
        
        # If this was a global preference change (langpref_*), just confirm
        if list_id.startswith("langpref_"):
            bg.add_task(whatsapp_service.send_message, from_phone,
                        f"🌍 Language set to *{language}*! I'll respond in {language} from now on. ✅")
            return
        
        # If this was from the PDF flow, show action buttons
        buttons = [
            {"id": "task_summarize", "title": "📝 Summarize"},
            {"id": "task_quiz", "title": "🧠 Quiz Me"},
            {"id": "task_flashcard", "title": "📇 Flashcards"},
        ]
        
        session = session_manager.get(from_phone)
        bg.add_task(
            whatsapp_service.send_interactive_buttons,
            from_phone,
            f"🌍 Language: *{language}* ✅\n\nWhat should I do with *{session.filename}*?",
            buttons
        )


async def handle_button_reply(from_phone: str, button_id: str, bg: BackgroundTasks):
    """Handles all button interactions."""
    
    # --- FEATURES / HELP / MENU BUTTONS ---
    if button_id == "btn_features":
        features_text = (
            "✨ *StudyBuddy AI — Features*\n\n"
            "💬 *AI Chat* — Ask anything like ChatGPT\n"
            "📄 *PDF Analysis* — Summarize any document\n"
            "🧠 *Quiz Mode* — Test knowledge with MCQs\n"
            "📇 *Flashcards* — Study key concepts\n"
            "📸 *Image Reader* — Read handwritten notes\n"
            "🎙️ *Voice Notes* — Transcribe recordings\n"
            "🔗 *URL Summary* — Summarize any link\n"
            "💻 *Code Helper* — Debug & explain code\n"
            "🌍 *8 Languages* — Multi-language support\n"
            "🔥 *Study Streaks* — Track your progress\n\n"
            "_Powered by Google Gemini 2.5 Flash_ ⚡"
        )
        bg.add_task(whatsapp_service.send_message, from_phone, features_text)
        return
    
    if button_id == "btn_help":
        bg.add_task(whatsapp_service.send_message, from_phone, HELP_MESSAGE)
        return
    
    if button_id == "btn_menu":
        bg.add_task(whatsapp_service.send_message, from_phone,
                    "🤖 *StudyBuddy AI — Quick Menu*\n\n"
                    "💬 Just type anything to chat\n"
                    "📄 Send a *PDF* → Summarize, quiz, flashcards\n"
                    "📸 Send a *photo* → Read notes & whiteboards\n"
                    "🎙️ Send a *voice note* → Transcription\n"
                    "🔗 Paste a *URL* → Summarize articles\n\n"
                    "⌨️ *Commands:* help | streak | clear | menu | lang")
        return
    
    # --- QUIZ ANSWER ---
    if button_id.startswith("quiz_"):
        answer = button_id.replace("quiz_", "").upper()
        await handle_quiz_answer(from_phone, answer, bg)
        return
    
    # --- FLASHCARD NAVIGATION ---
    if button_id == "flash_reveal":
        await handle_flash_reveal(from_phone, bg)
        return
    if button_id == "flash_next":
        await handle_flash_next(from_phone, bg)
        return
    
    # --- DOCUMENT TASK BUTTONS ---
    task_map = {
        "task_summarize": "summarize",
        "task_exam": "exam",
        "task_resume": "resume",
        "task_quiz": "quiz",
        "task_flashcard": "flashcard",
    }
    
    task_type = task_map.get(button_id)
    if not task_type:
        return
    
    session = session_manager.get(from_phone)
    if not session.media_id:
        bg.add_task(whatsapp_service.send_message, from_phone, 
                    "📄 I don't have an active document. Please upload a PDF first!")
        return
    
    processing_msg = random.choice(PROCESSING_MESSAGES)
    bg.add_task(whatsapp_service.send_message, from_phone, processing_msg)
    
    if task_type == "quiz":
        bg.add_task(orchestrate_quiz, from_phone)
    elif task_type == "flashcard":
        bg.add_task(orchestrate_flashcards, from_phone)
    else:
        bg.add_task(orchestrate_document_processing, from_phone, task_type)
    
    # Show more options after primary task
    bg.add_task(send_more_options, from_phone)


async def send_more_options(from_phone: str):
    """Sends additional action buttons after a task completes."""
    session = session_manager.get(from_phone)
    if not session.media_id:
        return
    
    await asyncio.sleep(3)
    
    buttons = [
        {"id": "task_exam", "title": "❓ Exam Qs"},
        {"id": "task_resume", "title": "💼 Optimize Resume"},
        {"id": "task_quiz", "title": "🧠 Quiz Me"},
    ]
    
    await whatsapp_service.send_interactive_buttons(
        from_phone,
        "✨ Want to do more with this document?",
        buttons
    )


# ==================== DOCUMENT PROCESSING ====================

async def orchestrate_document_processing(from_phone: str, task_type: str):
    """Downloads, extracts, and processes a PDF document."""
    session = session_manager.get(from_phone)
    filepath = None
    
    try:
        if session.doc_text_chunks:
            chunks = session.doc_text_chunks
        else:
            filepath = await whatsapp_service.download_media(session.media_id)
            if not filepath:
                await whatsapp_service.send_message(from_phone, "❌ Couldn't download the document.")
                return

            is_valid, msg = pdf_processor.validate_pdf(filepath)
            if not is_valid:
                await whatsapp_service.send_message(from_phone, f"❌ {msg}")
                return

            chunks = pdf_processor.extract_and_chunk_text(filepath)
            if not chunks:
                await whatsapp_service.send_message(from_phone, "❌ Couldn't extract text.")
                return
            
            session_manager.store_chunks(from_phone, chunks)

        language = session_manager.get_language(from_phone)
        result = await llm_service.process_document_pipeline(chunks, task_type=task_type, language=language)
        await whatsapp_service.send_message(from_phone, result)
        
        session_manager.record_activity(from_phone)
        db_logger.log_interaction(from_phone, session.filename, f"success_{task_type}")

    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Error: {str(e)}")
    finally:
        if filepath:
            pdf_processor.delete_file(filepath)


# ==================== QUIZ MODE ====================

async def orchestrate_quiz(from_phone: str):
    session = session_manager.get(from_phone)
    
    try:
        if not session.doc_text_chunks:
            filepath = await whatsapp_service.download_media(session.media_id)
            if not filepath:
                await whatsapp_service.send_message(from_phone, "❌ Couldn't download the document.")
                return
            chunks = pdf_processor.extract_and_chunk_text(filepath)
            session_manager.store_chunks(from_phone, chunks)
            pdf_processor.delete_file(filepath)
        
        language = session_manager.get_language(from_phone)
        questions = await llm_service.generate_quiz(session.doc_text_chunks, language=language)
        
        if not questions:
            await whatsapp_service.send_message(from_phone, "❌ Couldn't generate quiz. Please try again!")
            return
        
        session_manager.start_quiz(from_phone, questions)
        
        await whatsapp_service.send_message(from_phone, 
            f"🧠 *QUIZ TIME!* 🎯\n\n"
            f"I've prepared {len(questions)} questions from your document.\n"
            f"Let's test your knowledge! Good luck! 🍀")
        
        await send_quiz_question(from_phone)
        
    except Exception as e:
        logger.error(f"Quiz error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Quiz error: {str(e)}")


async def send_quiz_question(from_phone: str):
    q = session_manager.get_current_question(from_phone)
    if not q:
        return
    
    session = session_manager.get(from_phone)
    q_num = session.quiz_index + 1
    total = len(session.quiz_questions)
    
    question_text = (
        f"📋 *Question {q_num}/{total}*\n\n"
        f"{q['question']}\n\n"
        f"*A.* {q.get('A', '...')}\n"
        f"*B.* {q.get('B', '...')}\n"
        f"*C.* {q.get('C', '...')}"
    )
    
    buttons = [
        {"id": "quiz_a", "title": "A"},
        {"id": "quiz_b", "title": "B"},
        {"id": "quiz_c", "title": "C"},
    ]
    
    await whatsapp_service.send_interactive_buttons(from_phone, question_text, buttons)


async def handle_quiz_answer(from_phone: str, answer: str, bg: BackgroundTasks):
    is_correct, correct, is_last = session_manager.answer_quiz(from_phone, answer)
    
    if is_correct:
        feedback = "✅ *Correct!* Great job! 🎉"
    else:
        feedback = f"❌ *Wrong!* The correct answer was *{correct}*."
    
    await whatsapp_service.send_message(from_phone, feedback)
    
    if is_last:
        score, total, pct = session_manager.get_quiz_results(from_phone)
        
        if pct >= 80:
            grade = "🏆 *A+ — Outstanding!*"
        elif pct >= 60:
            grade = "👍 *B — Good job!*"
        elif pct >= 40:
            grade = "📚 *C — Keep studying!*"
        else:
            grade = "🔄 *Try again!*"
        
        result_msg = (
            f"\n{'🌟' if pct >= 80 else '💡'} *QUIZ COMPLETE!*\n\n"
            f"📊 *Score:* {score}/{total} ({pct}%)\n"
            f"{grade}\n\n"
            f"{'🔥 ' * min(score, 5)}"
        )
        await whatsapp_service.send_message(from_phone, result_msg)
        session_manager.record_activity(from_phone)
        streak_msg = session_manager.get_streak_message(from_phone)
        await whatsapp_service.send_message(from_phone, streak_msg)
    else:
        await asyncio.sleep(1)
        await send_quiz_question(from_phone)


# ==================== FLASHCARD MODE ====================

async def orchestrate_flashcards(from_phone: str):
    session = session_manager.get(from_phone)
    
    try:
        if not session.doc_text_chunks:
            filepath = await whatsapp_service.download_media(session.media_id)
            if not filepath:
                await whatsapp_service.send_message(from_phone, "❌ Couldn't download the document.")
                return
            chunks = pdf_processor.extract_and_chunk_text(filepath)
            session_manager.store_chunks(from_phone, chunks)
            pdf_processor.delete_file(filepath)
        
        language = session_manager.get_language(from_phone)
        cards = await llm_service.generate_flashcards(session.doc_text_chunks, language=language)
        
        if not cards:
            await whatsapp_service.send_message(from_phone, "❌ Couldn't generate flashcards. Please try again!")
            return
        
        session_manager.start_flashcards(from_phone, cards)
        
        await whatsapp_service.send_message(from_phone,
            f"📇 *FLASHCARD MODE* ✨\n\n"
            f"I've created {len(cards)} flashcards from your document.\n"
            f"Try to answer each one before revealing! 🧠")
        
        await send_flashcard(from_phone)
        
    except Exception as e:
        logger.error(f"Flashcard error: {str(e)}")
        await whatsapp_service.send_message(from_phone, f"❌ Flashcard error: {str(e)}")


async def send_flashcard(from_phone: str):
    card = session_manager.get_current_flashcard(from_phone)
    if not card:
        return
    
    session = session_manager.get(from_phone)
    card_num = session.flash_index + 1
    total = len(session.flashcards)
    
    card_text = (
        f"📇 *Card {card_num}/{total}*\n\n"
        f"❓ {card['front']}\n\n"
        f"_Think about it, then tap below to reveal..._"
    )
    
    buttons = [{"id": "flash_reveal", "title": "👀 Reveal Answer"}]
    await whatsapp_service.send_interactive_buttons(from_phone, card_text, buttons)


async def handle_flash_reveal(from_phone: str, bg: BackgroundTasks):
    card = session_manager.get_current_flashcard(from_phone)
    if not card:
        return
    
    session_manager.reveal_flashcard(from_phone)
    
    answer_text = f"💡 *Answer:*\n\n{card['back']}"
    await whatsapp_service.send_message(from_phone, answer_text)
    
    session = session_manager.get(from_phone)
    has_more = session.flash_index < len(session.flashcards) - 1
    
    if has_more:
        buttons = [{"id": "flash_next", "title": "➡️ Next Card"}]
        await whatsapp_service.send_interactive_buttons(from_phone, "Ready for the next one?", buttons)
    else:
        session_manager.next_flashcard(from_phone)
        await whatsapp_service.send_message(from_phone,
            "🎉 *All flashcards complete!* 🏆\n\n"
            "Great session! Send a new document or just chat with me! 💬")
        session_manager.record_activity(from_phone)
        streak_msg = session_manager.get_streak_message(from_phone)
        await whatsapp_service.send_message(from_phone, streak_msg)


async def handle_flash_next(from_phone: str, bg: BackgroundTasks):
    session_manager.next_flashcard(from_phone)
    await send_flashcard(from_phone)
