# Voice Assistant Spec — English · MiniMax + ElevenLabs

## Overview
Personal AI voice assistant. Wake on clap or keyword. Voice in, voice out. Browser automation + screen vision. Pure English personality.

**Stack:** FastAPI + MiniMax (LLM + Vision) + ElevenLabs (TTS) + Playwright + sounddevice/numpy

**Platform:** Linux (primary), macOS (compatible)

---

## Features

### Wake & Voice IO
- [ ] **Clap trigger** — double-clap detection via `sounddevice + numpy`
- [ ] **Keyword wake** — configurable wake word ("Hey Assistant", "OK Assistant")
- [ ] **Push-to-talk** — hold spacebar or button to talk
- [ ] **Voice in** — browser Web Speech API (no API key needed)
- [ ] **Voice out** — ElevenLabs TTS, configurable voice ID
- [ ] **Continuous listening** — optional mode, don't require repeat wake

### Intelligence
- [ ] **MiniMax LLM** — text generation, reasoning, tool decisions
- [ ] **MiniMax Vision** — screenshot analysis (describe what's on screen)
- [ ] **Proactive greeting** — weather + date/time + task summary on wake
- [ ] **Context memory** — retains conversation context within session
- [ ] **Tool execution** — browser, search, app launching

### Browser Automation
- [ ] **Open URL** — launch browser to specific site
- [ ] **Search + Summarize** — search query → results → read content → summarize
- [ ] **Click / interact** — element-level interaction via Playwright
- [ ] **Screenshots** — full page capture for vision analysis

### Screen Vision
- [ ] **What's on my screen?** — take screenshot → MiniMax Vision → describe
- [ ] **Read this for me** — capture screen region → read text

### App Launching (OS-native)
- [ ] **Workspace launch** — single trigger opens your full workspace apps
- [ ] **Window snapping** — Linux: `xdotool` / `wmctrl`; macOS: `cliclick`
- [ ] **Spotify** — play track or podcast via `spotify-cli` or URI open
- [ ] **App control** — open any installed app via deep link

### Personality
- [ ] **Pure English** — no German, no code-switching
- [ ] **Helpful, calm** — not sarcastic, not overly formal
- [ ] **Concise** — short responses, expand only when asked
- [ ] **Configurable** — personality strength, verbosity, response length via config

### Configuration
- [ ] **config.json** — API keys, paths, preferences
- [ ] **env vars** — `MINIMAX_API_KEY`, `ELEVENLABS_API_KEY` (safer than config file)
- [ ] **Voice selection** — ElevenLabs voice ID
- [ ] **City** — for weather greeting
- [ ] **Custom wake word** — configurable phrase
- [ ] **Workspace apps** — list of apps to launch on wake

---

## Architecture

```
User (speak) → Chrome (Web Speech API) → FastAPI Server → MiniMax (LLM)
                                                      ↓
                               ElevenLabs TTS / Playwright / Screenshot
```

```
Wake Trigger → sounddevice (clap/keyword) → FastAPI Server (start session)
```

---

## File Structure

```
voice-assistant/
├── server.py              # FastAPI backend — brain
├── config.json           # Your config (gitignored)
├── config.example.json   # Template
├── requirements.txt      # Python deps
├── browser_tools.py      # Playwright automation
├── screen_capture.py     # Screenshot + MiniMax Vision
├── audio_tools.py        # ElevenLabs TTS
├── wake/
│   ├── clap_trigger.py   # Double-clap detection
│   └── keyword_trigger.py # Keyword spotting
├── scripts/
│   ├── launch-workspace.sh # Linux workspace launcher + window snap
│   └── install-deps.sh     # Dependency installer
├── frontend/
│   ├── index.html        # Web UI
│   ├── main.js           # Speech recognition + WebSocket + audio playback
│   └── style.css         # Dark theme, minimal
├── CLAUDE.md              # Claude Code setup instructions
└── SETUP.md               # Manual setup guide
```

---

## Open Questions

1. **Local STT** — use Web Speech API (browser, free) or add MiniMax-STT for offline?
2. **Continuous listening** — yes/no? Tradeoff: more compute, faster responses vs privacy
3. **Memory persistence** — flat file (JSON) or bring in a simple SQLite layer?
4. **Mobile mic** — is this a priority?
5. **Platform target** — Linux primary only, or macOS too?

---

## Out of Scope (v1)
- Windows-only features (PowerShell/Win32)
- Multi-user / voice profiles
- Plugin system
- macOS automatic adaptation