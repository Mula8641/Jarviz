# Voice Assistant — Claude Code Setup

Give your agent this file and say:

> "Set up the Voice Assistant project for me."

The agent will read CONFIG.md, install dependencies, and configure API keys.

## Project Structure

```
voice-assistant/
├── server.py          # FastAPI + WebSocket — start here
├── config.py          # Config loader (env > json)
├── config.example.json # Template
├── llm.py             # MiniMax LLM
├── prompts.py         # System prompt
├── audio_tools.py     # ElevenLabs TTS
├── browser_tools.py   # Playwright automation
├── screen_capture.py  # Windows GDI+ capture
├── vision.py          # MiniMax Vision
├── context.py         # Conversation history
├── memory.py          # SQLite memory
├── logger.py          # Structured logging
├── errors.py          # Custom exceptions
├── wake/
│   ├── clap_trigger.py   # Double-clap detection
│   └── trigger_server.py # UDP wake dispatcher
├── frontend/
│   ├── index.html
│   ├── main.js
│   └── style.css
├── scripts/
│   ├── launch-session.ps1
│   ├── snap-windows.ps1
│   └── install-deps.ps1
├── SETUP.md
└── REQUIREMENTS.txt
```

## Key Decisions

- **Brain:** MiniMax-M2.7 via REST API
- **Voice:** ElevenLabs TTS (stream, not webhook)
- **STT:** Web Speech API (browser-native, no key)
- **Browser:** Playwright (headless Chromium)
- **Memory:** SQLite (evolvable)
- **Wake:** Double-clap via sounddevice + numpy

## Files to Edit

| File | What to set |
|------|------------|
| `config.json` | API keys, city, user name, apps |
| `prompts.py` | Personality, greeting style |
| `frontend/style.css` | Theme colors, orb animation |
| `scripts/launch-session.ps1` | Your workspace apps |
| `scripts/snap-windows.ps1` | Window snapping (Win32 API) |