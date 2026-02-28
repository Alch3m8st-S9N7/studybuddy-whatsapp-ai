"""
Centralized Session Manager for the WhatsApp AI Bot.
Manages per-user state: documents, quiz progress, flashcards, streaks, and preferences.
"""
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from app.utils.logger import logger


class UserSession:
    """Represents a single user's session state."""
    def __init__(self, phone: str):
        self.phone = phone
        self.first_visit = True
        
        # Document state
        self.media_id: Optional[str] = None
        self.filename: Optional[str] = None
        self.doc_text_chunks: Optional[List[str]] = None
        
        # Language preference
        self.language: str = "English"
        
        # Conversation history (for context-aware chat)
        self.chat_history: List[Dict[str, str]] = []
        self.max_history: int = 20  # Keep last 20 messages
        
        # Quiz state
        self.quiz_questions: List[Dict] = []
        self.quiz_index: int = 0
        self.quiz_score: int = 0
        self.quiz_active: bool = False
        
        # Flashcard state
        self.flashcards: List[Dict] = []
        self.flash_index: int = 0
        self.flash_active: bool = False
        self.flash_revealed: bool = False
        
        # Study streak
        self.docs_processed: int = 0
        self.last_activity_date: Optional[date] = None
        self.streak: int = 0


class SessionManager:
    """In-memory session manager for all users."""
    
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
    
    def get(self, phone: str) -> UserSession:
        """Get or create a session for a user."""
        if phone not in self._sessions:
            self._sessions[phone] = UserSession(phone)
        return self._sessions[phone]
    
    def is_first_visit(self, phone: str) -> bool:
        """Check if this is the user's first interaction."""
        session = self.get(phone)
        if session.first_visit:
            session.first_visit = False
            return True
        return False
    
    # --- Document Management ---
    def store_document(self, phone: str, media_id: str, filename: str):
        session = self.get(phone)
        session.media_id = media_id
        session.filename = filename
        session.doc_text_chunks = None  # Reset chunks for new doc
    
    def store_chunks(self, phone: str, chunks: List[str]):
        self.get(phone).doc_text_chunks = chunks
    
    def get_document(self, phone: str) -> tuple:
        session = self.get(phone)
        return session.media_id, session.filename
    
    # --- Language ---
    def set_language(self, phone: str, language: str):
        self.get(phone).language = language
    
    def get_language(self, phone: str) -> str:
        return self.get(phone).language
    
    # --- Conversation History ---
    def add_message(self, phone: str, role: str, content: str):
        """Adds a message to the user's chat history."""
        session = self.get(phone)
        session.chat_history.append({"role": role, "content": content})
        # Trim to max size
        if len(session.chat_history) > session.max_history:
            session.chat_history = session.chat_history[-session.max_history:]
    
    def get_history(self, phone: str) -> List[Dict[str, str]]:
        """Returns the user's recent chat history."""
        return self.get(phone).chat_history
    
    def clear_history(self, phone: str):
        self.get(phone).chat_history = []
    
    # --- Quiz Management ---
    def start_quiz(self, phone: str, questions: List[Dict]):
        session = self.get(phone)
        session.quiz_questions = questions
        session.quiz_index = 0
        session.quiz_score = 0
        session.quiz_active = True
    
    def get_current_question(self, phone: str) -> Optional[Dict]:
        session = self.get(phone)
        if session.quiz_index < len(session.quiz_questions):
            return session.quiz_questions[session.quiz_index]
        return None
    
    def answer_quiz(self, phone: str, answer: str) -> tuple:
        """Returns (is_correct, correct_answer, is_last_question)."""
        session = self.get(phone)
        if not session.quiz_active or session.quiz_index >= len(session.quiz_questions):
            return False, "", True
        
        q = session.quiz_questions[session.quiz_index]
        correct = q.get("correct", "").upper()
        is_correct = answer.upper() == correct
        
        if is_correct:
            session.quiz_score += 1
        
        session.quiz_index += 1
        is_last = session.quiz_index >= len(session.quiz_questions)
        
        if is_last:
            session.quiz_active = False
        
        return is_correct, correct, is_last
    
    def get_quiz_results(self, phone: str) -> tuple:
        """Returns (score, total, percentage)."""
        session = self.get(phone)
        total = len(session.quiz_questions)
        score = session.quiz_score
        pct = round((score / total) * 100) if total > 0 else 0
        return score, total, pct
    
    # --- Flashcard Management ---
    def start_flashcards(self, phone: str, cards: List[Dict]):
        session = self.get(phone)
        session.flashcards = cards
        session.flash_index = 0
        session.flash_active = True
        session.flash_revealed = False
    
    def get_current_flashcard(self, phone: str) -> Optional[Dict]:
        session = self.get(phone)
        if session.flash_index < len(session.flashcards):
            return session.flashcards[session.flash_index]
        return None
    
    def reveal_flashcard(self, phone: str):
        self.get(phone).flash_revealed = True
    
    def next_flashcard(self, phone: str) -> bool:
        """Move to next card. Returns True if there are more cards."""
        session = self.get(phone)
        session.flash_index += 1
        session.flash_revealed = False
        if session.flash_index >= len(session.flashcards):
            session.flash_active = False
            return False
        return True
    
    # --- Study Streak ---
    def record_activity(self, phone: str):
        """Records a doc processed and updates the streak."""
        session = self.get(phone)
        today = date.today()
        
        session.docs_processed += 1
        
        if session.last_activity_date is None:
            session.streak = 1
        elif session.last_activity_date == today:
            pass  # Already counted today
        elif (today - session.last_activity_date).days == 1:
            session.streak += 1
        else:
            session.streak = 1  # Reset streak
        
        session.last_activity_date = today
    
    def get_streak_message(self, phone: str) -> str:
        """Returns a motivational streak message."""
        session = self.get(phone)
        streak = session.streak
        total = session.docs_processed
        
        if streak <= 1:
            return f"📄 *Documents studied:* {total}"
        
        fire = "🔥" * min(streak, 5)
        
        if streak >= 7:
            msg = f"{fire} *{streak}-day study streak!* You're UNSTOPPABLE! 🏆\n📄 Total docs: {total}"
        elif streak >= 3:
            msg = f"{fire} *{streak}-day streak!* Keep the momentum going! 💪\n📄 Total docs: {total}"
        else:
            msg = f"{fire} *{streak}-day streak!* Great consistency! ✨\n📄 Total docs: {total}"
        
        return msg


# Bot Personality Messages
BOT_NAME = "StudyBuddy AI"

WELCOME_MESSAGE = f"""🎓 *Welcome to {BOT_NAME}!* 🤖✨

I'm your personal AI assistant on WhatsApp, powered by *Google Gemini 2.5*! Think of me as ChatGPT, but right here in your chats. Here's what I can do:

💬 *Ask me anything* — Math, science, coding, advice, general knowledge
📄 *Upload a PDF* → Summarize, quiz, or flashcards
📸 *Send a photo* → I read handwritten notes & whiteboards
🎙️ *Voice note* → Instant transcription & study notes
🔗 *Paste a URL* → I'll summarize any article or webpage
💻 *Code help* → Debug, explain, or write code for you

Just type anything to get started! 🚀"""

HELP_MESSAGE = f"""📚 *{BOT_NAME} — Command Guide*

💬 *Chat* → Ask me literally anything
📄 *PDF* → Upload for summaries, quizzes, flashcards
📸 *Image* → Photo of notes, whiteboard, diagrams
🎙️ *Voice* → Record → transcription + notes
🔗 *URL* → Paste link → get a summary
💻 *Code* → Start with "code:" for code help

*Special Commands:*
• *help* — This guide
• *streak* — Study streak tracker 🔥
• *menu* — Feature menu
• *clear* — Reset chat memory
• *lang* — Change language preference

_Powered by Google Gemini 2.5 Flash_ ⚡"""

PROCESSING_MESSAGES = [
    "🧠 Thinking... This is a good one!",
    "📖 Diving deep into this... Give me a sec!",
    "✨ Processing with AI magic... Almost there!",
    "🔍 Analyzing... Hang tight!",
    "💡 Working on it... Your answer is coming!",
]


# Singleton
session_manager = SessionManager()
