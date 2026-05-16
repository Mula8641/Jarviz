# Voice Assistant — Advancement Specs

## Priority Order: A → B → C → D

---

## Advancement A — Keyword Wake

**Problem:** Clap trigger is unreliable in noisy environments. Users want "Hey Assistant" style wake.

**What it does:**
- Detect a configurable keyword phrase ("Hey Assistant", "OK Assistant", etc.)
- Uses a lightweight local model (Silero VAD + smaller wake model) OR browser Web Speech API as fallback
- Runs in background thread alongside clap trigger (both active)
- Configurable sensitivity and phrase in `config.json`

**Files touched:**
- `wake/keyword_trigger.py` (new — ~150 lines)
- `wake/__init__.py` (update)
- `server.py` (integrate)
- `config.example.json` (add keyword field)

**Dependencies:** `silero-vad` (optional), else use Web Speech API loopback

**Pros:** More reliable than clap, natural UX
**Cons:** Requires microphone always-on; potential false triggers in TV audio
**Verdict:** ✅ Worth building — high UX impact, ~150 lines

---

## Advancement B — Cross-Session Memory

**Problem:** Memory.py stores conversation turns, but doesn't remember user preferences, habits, or past sessions.

**What it does:**
- SQLite table `user_memory`: key/value pairs (long-term facts about user)
- On shutdown: summarize session → store key facts
- On startup: inject recent memory into system prompt
- Example: "User prefers short answers" / "User likes morning briefings" / "User's boss name is Alex"

**Files touched:**
- `memory.py` (extend — add `user_memory` table + `set_fact()` / `get_facts()`)
- `prompts.py` (inject facts into system prompt)
- `server.py` (save facts on shutdown via atexit/register_shutdown)

**New methods:**
```python
def set_fact(key: str, value: str): ...
def get_facts() -> dict: ...
def extract_facts(conversation: list) -> list[str]: ... # LLM picks key facts
```

**Pros:** Evolves with user, makes assistant feel personal
**Cons:** Needs LLM to extract facts (extra API call on shutdown)
**Verdict:** ✅ Worth building — ~100 lines, high personal feel

---

## Advancement C — Text Input Mode

**Problem:** Voice-only is limiting — noisy environments, accessibility, quiet offices.

**What it does:**
- Add text input box to `frontend/index.html` alongside mic button
- `frontend/main.js` sends typed text via same WebSocket path as voice
- Frontend shows toggle: 🎤 Voice mode / ⌨️ Text mode
- TTS still speaks responses in both modes

**Files touched:**
- `frontend/index.html` (add input box + mode toggle)
- `frontend/main.js` (add text path, mode switching)
- `frontend/style.css` (style input + toggle)

**Pros:** Zero new backend — just a new frontend channel
**Cons:** Minor UX complexity
**Verdict:** ✅ Worth building — ~80 lines, huge accessibility win

---

## Advancement D — Ollama Local Fallback

**Problem:** MiniMax quota runs out; no fallback for offline/simple queries.

**What it does:**
- Check if MiniMax fails (rate limit / network error) → fall back to Ollama
- `llm.py`: try MiniMax → if error and `OLLAMA_BASE_URL` is set → call Ollama
- Ollama serves simple queries (weather, time, definitions) for free
- MiniMax handles complex reasoning, browser tasks

**Config additions:**
```json
{
  "ollama_base_url": "http://localhost:11434",
  "ollama_model": "llama3.2",
  "fallback_to_ollama": true
}
```

**Files touched:**
- `llm.py` (add `chat_with_fallback()` — try MiniMax, retry with Ollama)
- `config.example.json` (add Ollama fields)

**Pros:** Quota protection, offline resilience, cost saving
**Cons:** Requires Ollama installed (~5min setup); quality drop for complex tasks
**Verdict:** ✅ Worth building — ~80 lines, strong reliability gain

---

## Summary Table

| Advancement | Lines (est.) | Impact | Priority |
|-------------|-------------|--------|----------|
| A — Keyword Wake | ~150 | High UX | 1 |
| B — Cross-Session Memory | ~100 | High personal feel | 2 |
| C — Text Input Mode | ~80 | High accessibility | 3 |
| D — Ollama Fallback | ~80 | High reliability | 4 |

---

## Recommended Order

A → B → C → D

Each builds on previous cleanly. No conflicts. All modular.

After these 4 additions, consider: **Plugin System** (Advancement E) and **Mobile Mic** (Advancement F).

---

## Decision Needed

Want me to proceed with all 4? Or pick specific ones?