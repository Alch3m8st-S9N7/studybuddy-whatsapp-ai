# 🎓 StudyBuddy AI — WhatsApp AI Assistant

> **ChatGPT-level AI assistant inside WhatsApp**, powered by Google Gemini 2.5 Flash. Upload PDFs, snap photos, record voice notes, take quizzes — all from your favorite messaging app.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green?logo=fastapi)
![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-orange?logo=google)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Cloud_API-25D366?logo=whatsapp)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 **AI Chat** | Ask anything — math, science, coding, advice. Full conversation memory |
| 📄 **PDF Analysis** | Upload any PDF → Summarize, generate exam questions, optimize resumes |
| 🧠 **Interactive Quiz** | AI generates MCQ questions, sends them one-by-one, grades your score |
| 📇 **Flashcards** | Study key concepts with interactive flip cards |
| 📸 **Image Reader** | Snap a photo of handwritten notes or whiteboards → AI reads & summarizes |
| 🎙️ **Voice Notes** | Send a recording → Get transcription + study notes |
| 🔗 **URL Summarizer** | Paste any link → Get an instant article summary |
| 💻 **Code Helper** | Debug, explain, or generate code |
| 🌍 **8 Languages** | English, Hindi, Spanish, French, German, Chinese, Japanese, Arabic |
| 🔥 **Study Streaks** | Track consecutive-day usage with motivational messages |
| ⚡ **Rich UX** | Emoji reactions, blue ticks, interactive buttons & lists |

---

## 🏗️ Architecture

```
whatsapp-ai-bot/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment config (Pydantic Settings)
│   ├── routes/
│   │   └── webhook.py          # WhatsApp webhook handler (brain of the bot)
│   ├── services/
│   │   ├── whatsapp.py         # WhatsApp Cloud API integration
│   │   ├── llm_service.py      # Gemini & Groq multi-LLM service
│   │   ├── pdf_processor.py    # PDF validation, extraction, chunking
│   │   ├── session_manager.py  # User sessions, quiz, flashcards, streaks
│   │   ├── db_logger.py        # Optional database logging
│   │   └── payment.py          # Optional Razorpay integration
│   ├── prompts/
│   │   └── templates.py        # AI prompt templates for all features
│   └── utils/
│       ├── logger.py           # Logging utility
│       └── rate_limit.py       # Per-user rate limiting
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/studybuddy-whatsapp-ai.git
cd studybuddy-whatsapp-ai
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
- `WHATSAPP_API_TOKEN` — From [Meta Developer Dashboard](https://developers.facebook.com)
- `WHATSAPP_PHONE_NUMBER_ID` — Your WhatsApp Business phone number ID
- `GEMINI_API_KEY` — From [Google AI Studio](https://aistudio.google.com)

### 3. Run
```bash
python -m uvicorn app.main:app --reload
```

### 4. Expose to Internet
```bash
npx localtunnel --port 8000
```
Use the generated URL as your webhook in Meta Developer Dashboard → WhatsApp → Configuration.

---

## 🤖 How It Works

1. User sends a message on WhatsApp (text, PDF, image, voice, or URL)
2. Meta's Cloud API forwards it to our webhook
3. FastAPI routes it to the appropriate handler
4. Google Gemini 2.5 Flash processes the content
5. Response is sent back via WhatsApp with rich formatting

---

## 📱 WhatsApp Commands

| Command | Action |
|---------|--------|
| `help` | Show command guide |
| `menu` | Feature overview |
| `streak` | View study streak |
| `lang` | Change language |
| `clear` | Reset chat memory |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **AI Engine:** Google Gemini 2.5 Flash (primary), Groq/xAI (fallback)
- **Messaging:** WhatsApp Cloud API (Meta Graph API)
- **PDF Processing:** PyMuPDF (fitz)
- **Deployment:** Docker, Render.com

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

Built with ❤️ by [Sarthak](mailto:sonusarhan007@gmail.com)
