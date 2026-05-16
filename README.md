# Voice Assistant

Personal AI voice assistant for Windows. Speak, listen, control your browser and screen.

## Stack

- **Brain:** MiniMax LLM + Vision
- **Voice:** ElevenLabs TTS + Web Speech API
- **Automation:** Playwright
- **Backend:** FastAPI + WebSockets
- **Platform:** Windows

## Quick Start

```bash
# 1. Clone
git clone <your-repo-url>
cd voice-assistant

# 2. Install deps
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp config.example.json config.json
# Edit config.json with your API keys

# 4. Run
python server.py

# 5. Open browser
# Chrome → http://localhost:8340
# Click the mic button and speak
```

## Features

- 🎤 Voice in / Voice out
- 👀 Screen vision (describe what's on your screen)
- 🌐 Browser automation (search, open, interact)
- 🔔 Clap wake trigger
- 💬 Conversational memory
- 🚀 One-trigger workspace launch

## Requirements

- Python 3.10+
- Windows 10/11
- Google Chrome
- MiniMax API key
- ElevenLabs API key