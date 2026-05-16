# Jarviz Voice Assistant

Personal AI voice assistant for Windows. Speak, listen, control your browser and screen.

## Stack

- **Brain:** MiniMax LLM + Vision (auto-fallback to Ollama)
- **Voice:** ElevenLabs TTS + Web Speech API
- **Automation:** Playwright
- **Backend:** FastAPI + WebSockets
- **Platform:** Windows

## Quick Start — One Command

Double-click `launch-everything.bat` and everything installs and starts automatically.

Or manual setup:

```bash
# 1. Clone
git clone https://github.com/Mula8641/Jarviz.git
cd voice-assistant

# 2. Install deps
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp config.example.json config.json
# Edit config.json with your API keys, or add them via the Settings UI

# 4. Run
python server.py

# 5. Open browser
# Chrome → http://localhost:8340
# Click mic to speak, or type in text mode
```

> **First run:** `launch-everything.bat` will create a virtual environment, install all dependencies, download Chromium, and start the server. No manual steps needed after that.

## Features

- 🎤 **Voice in / Voice out** — push-to-talk or continuous wake
- 👀 **Screen vision** — describe what's on your screen
- 🌐 **Browser automation** — search, open, interact with sites
- 🔔 **Clap wake trigger** — clap hands to activate
- 🎵 **Keyword wake** — say "Hey Assistant" to activate (configurable)
- 💬 **Cross-session memory** — remembers facts about you over time
- ⌨️ **Text input mode** — type commands when voice isn't convenient
- 🤖 **Ollama fallback** — works offline when MiniMax rate limits
- 🚀 **One-trigger launch** — launch everything with one button
- ⚙️ **Settings UI** — add API keys directly from the browser