# Voice Assistant — Development Plan

## Principles
- Files ≤ 800 lines, single responsibility
- After every 3 stages: live test checkpoint
- Modular: each component independently testable
- Windows-first platform

---

## Stage Groups & Checkpoints

### GROUP A — Foundation (1–3) ✅
**Goal:** Project scaffold, config, basic server, voice IO shell

**Checkpoint A:** Server starts, Web Speech API transcribes, ElevenLabs TTS responds, WebSocket connects

---

**Stage 1 — Project Scaffold + Config** ✅
- [x] `server.py` — FastAPI skeleton, CORS, health endpoint
- [x] `config.example.json` — template with all keys/paths
- [x] `config.py` — loader (env vars win over json)
- [x] `requirements.txt` — all Python deps
- [x] `frontend/index.html` — minimal web UI shell
- [x] `frontend/main.js` — WebSocket client stub
- [x] `frontend/style.css` — dark theme stub
- [x] `.gitignore`
- [x] `README.md` — quick start

**Stage 2 — Voice In/Out** ✅
- [x] `frontend/main.js` — Web Speech API mic → text → WebSocket send
- [x] `server.py` — WebSocket endpoint receives transcript
- [x] `audio_tools.py` — ElevenLabs TTS, text → audio bytes
- [x] `server.py` — TTS queue, send audio back via WebSocket
- [x] `frontend/main.js` — receive audio → play in browser
- [x] **Mute button** — JS toggle, stops speech recognition

**Stage 3 — Logging + Error Shell** ✅
- [x] `logger.py` — structured logging (console + file)
- [x] `server.py` — add logging everywhere
- [x] `errors.py` — custom exceptions, retry logic shell

---

### GROUP B — Brain + Wake (4–6) ✅
**Goal:** MiniMax LLM connected, system prompt personality, clap trigger ready

**Checkpoint B:** "Hello" spoken → MiniMax responds via ElevenLabs, clap detection starts listening

---

**Stage 4 — MiniMax LLM Integration** ✅
- [x] `llm.py` — MiniMax API client (chat completion)
- [x] `prompts.py` — system prompt builder (English, helpful, calm)
- [x] `server.py` — connect WebSocket transcript → LLM → TTS

**Stage 5 — Wake System** ✅
- [x] `wake/clap_trigger.py` — sounddevice + numpy double-clap
- [x] `wake/__init__.py`
- [x] `wake/trigger_server.py` — UDP socket fires when wake detected
- [x] `server.py` — wake trigger integration

**Stage 6 — Personality + Context** ✅
- [x] `prompts.py` — helpful, calm, concise English personality
- [x] `context.py` — in-memory conversation history (list of messages)
- [x] `server.py` — inject context into MiniMax prompt
- [x] `memory.py` — SQLite schema + read/write

---

### GROUP C — Browser Automation (7–9) ✅
**Goal:** Playwright browsing, search, summarize, element interaction

**Checkpoint C:** "Search for AI news" → browser opens, searches, returns summarized results

---

**Stage 7 — Playwright Browser Shell** ✅
- [x] `browser_tools.py` — Playwright setup, browser launch/close
- [x] `server.py` — add `/browse/open` endpoint

**Stage 8 — Search + Summarize** ✅
- [x] `browser_tools.py` — `search(query)` → extract result snippets
- [x] `browser_tools.py` — `read_page()` → full text extraction
- [x] `server.py` — `/browse/search` endpoint

**Stage 9 — Element Interaction** ✅
- [x] `browser_tools.py` — `click()`, `type()`, `scroll()`, `take_screenshot()`
- [x] `server.py` — `/browse/interact` endpoint
- [x] `screenshot_cache.py` — temp store screenshots for vision

---

### GROUP D — Screen Vision + Polish (10–12) ✅
**Goal:** Screenshot → MiniMax Vision → describe, clap+socket integration, workspace launch

**Checkpoint D:** "What's on my screen?" → screenshot → MiniMax Vision → spoken description

---

**Stage 10 — Screen Vision** ✅
- [x] `screen_capture.py` — `capture_screen()` Windows GDI+pywin32
- [x] `vision.py` — MiniMax Vision API (MiniMax-V01)
- [x] `server.py` — `/vision/describe` endpoint

**Stage 11 — Workspace Launch + Window Snap** ✅
- [x] `scripts/launch-session.ps1` — opens workspace apps
- [x] `scripts/snap-windows.ps1` — PowerShell Win32 quadrant snapping
- [x] `server.py` — `/workspace/launch` + `/workspace/snap` endpoints

**Stage 12 — Final Polish** ✅
- [x] `SETUP.md` — Windows install steps
- [x] `CLAUDE.md` — Claude Code setup instructions
- [x] `scripts/install-deps.ps1` — automated dependency installer

---

## File Map

```
voice-assistant/
├── server.py              # FastAPI + WebSocket hub  (280 lines)
├── config.py             # Config loader (env > json) (~30 lines)
├── config.example.json   # Template (~16 lines)
├── requirements.txt      # Pinned deps (~10 lines)
├── logger.py             # Structured logging (~33 lines)
├── errors.py             # Custom exceptions + retries (~48 lines)
├── llm.py                # MiniMax chat + vision (~84 lines)
├── prompts.py           # System prompt builder (~48 lines)
├── audio_tools.py        # ElevenLabs TTS (~40 lines)
├── browser_tools.py      # Playwright automation (~134 lines)
├── screen_capture.py     # Windows screen capture (~93 lines)
├── vision.py             # MiniMax Vision (~29 lines)
├── context.py           # In-memory conversation history (~31 lines)
├── memory.py            # SQLite memory layer (~61 lines)
├── screenshot_cache.py  # Temp screenshot storage (~28 lines)
├── wake/
│   ├── __init__.py
│   ├── clap_trigger.py   # Double-clap detection (~120 lines)
│   └── trigger_server.py # UDP wake dispatcher (~50 lines)
├── frontend/
│   ├── index.html       # Web UI (~24 lines)
│   ├── main.js          # WS client + speechrecognition (~125 lines)
│   └── style.css        # Dark theme (~90 lines)
├── scripts/
│   ├── launch-session.ps1   (~15 lines)
│   ├── snap-windows.ps1     (~40 lines)
│   └── install-deps.ps1     (~10 lines)
├── CLAUDE.md
├── SETUP.md
├── README.md
└── .gitignore
```

---

## Testing Policy
- After Group A: say "hello" → hear TTS response
- After Group B: clap triggers wake greeting
- After Group C: browser search returns summarized text
- After Group D: screen vision produces spoken description
- Every file: Python syntax check before commit

---

## Dependencies (pinned)

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
websockets>=12.0
python-sounddevice>=0.5.0
numpy>=1.26.0
playwright>=1.44.0
pywin32>=306; platform_system=="Windows"
pillow>=10.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
aiosqlite>=0.20.0
```