"""Voice Assistant server — FastAPI + WebSocket hub."""
import truststore
truststore.inject_into_ssl()
import asyncio
import atexit
import base64
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
from pathlib import Path
import threading

from config import config
from logger import setup_logger
from audio_tools import text_to_speech
from prompts import system_prompt, greeting_prompt
from context import ConversationContext
from memory import add_turn, get_facts, clear_facts
from browser_tools import get_browser, shutdown_browser
from screenshot_cache import storeScreenshot
from wake.trigger_server import start_trigger_server
import agent

log = setup_logger("server")

active_ws = None
conversation = ConversationContext()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clap trigger
    try:
        from wake.clap_trigger import ClapTrigger
        trigger = ClapTrigger(
            threshold=config.get("clap_threshold", 0.15),
            max_gap=config.get("clap_max_gap", 1.2),
        )
        trigger.set_callback(lambda: _trigger_wake())
        trigger.start()
        log.info("Clap trigger started")
        app.state.clap_trigger = trigger
    except Exception as e:
        log.warning("Could not start clap trigger: %s", e)

    # Keyword trigger (optional)
    try:
        if config.get("keyword_enabled", False):
            from wake.keyword_trigger import KeywordTrigger
            kw_trigger = KeywordTrigger(
                phrase=config.get("keyword_phrase", "hey assistant"),
            )
            kw_trigger.set_callback(lambda: _trigger_wake())
            kw_trigger.start()
            log.info("Keyword trigger started: '%s'", config.get("keyword_phrase"))
            app.state.keyword_trigger = kw_trigger
        else:
            log.info("Keyword trigger disabled (keyword_enabled=false)")
    except Exception as e:
        log.warning("Could not start keyword trigger: %s", e)

    # UDP trigger server
    stop_server = start_trigger_server(callback=lambda msg: _trigger_wake())
    app.state.stop_trigger = stop_server

    # Reminder scheduler
    reminder_task = asyncio.create_task(_reminder_scheduler())
    app.state.reminder_task = reminder_task

    yield

    # Shutdown
    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass
    if hasattr(app.state, "clap_trigger"):
        app.state.clap_trigger.stop()
    if hasattr(app.state, "keyword_trigger"):
        app.state.keyword_trigger.stop()
    if hasattr(app.state, "stop_trigger"):
        app.state.stop_trigger()
    shutdown_browser()

async def _reminder_scheduler():
    """Check for due reminders every 30 seconds and speak them aloud."""
    while True:
        await asyncio.sleep(30)
        try:
            from memory import get_due_reminders, mark_reminder_done
            due = get_due_reminders()
            for reminder in due:
                mark_reminder_done(reminder["id"])
                if active_ws:
                    msg = f"Reminder: {reminder['message']}"
                    audio = text_to_speech(msg)
                    if audio:
                        await active_ws.send_json({
                            "type": "audio",
                            "data": base64.b64encode(audio).decode(),
                        })
                    await active_ws.send_json({"type": "status", "text": msg})
                    log.info("Reminder delivered: %s", reminder["message"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("Reminder check error: %s", e)


def _trigger_wake():
    global active_ws
    import asyncio
    if active_ws:
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(_send_greeting(active_ws), loop)

async def _send_greeting(ws: WebSocket):
    try:
        greet_text = greeting_prompt()
        greet_audio = text_to_speech(greet_text)
        if greet_audio:
            await ws.send_json({
                "type": "audio",
                "data": base64.b64encode(greet_audio).decode(),
            })
        await ws.send_json({"type": "status", "text": "Wake triggered — listening"})
    except Exception as e:
        log.warning("Greeting send failed: %s", e)

def _save_session_facts():
    """On shutdown: extract notable facts from recent conversation."""
    try:
        from memory import get_conversation, extract_and_store_facts
        conv = get_conversation(limit=30)
        if conv:
            extract_and_store_facts(conv)
            log.info("Session facts saved on shutdown")
    except Exception as e:
        log.warning("Could not save session facts: %s", e)

atexit.register(_save_session_facts)

# --- FastAPI App ---
app = FastAPI(title="Voice Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files at /static (mount at /static, NOT /, to avoid shadowing API routes)
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="static")


@app.get("/")
async def serve_index():
    """Serve the main UI page."""
    from fastapi.responses import FileResponse
    index_path = frontend_dir / "index.html"
    return FileResponse(str(index_path))


# --- WebSocket ---
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global active_ws, conversation
    await ws.accept()
    active_ws = ws
    log.info("WebSocket client connected")

    greet_audio = text_to_speech(greeting_prompt())
    if greet_audio:
        await ws.send_json({
            "type": "audio",
            "data": base64.b64encode(greet_audio).decode(),
        })

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "transcript":
                text = data.get("text", "").strip()
                if not text:
                    continue

                log.info("Transcript: %s", text)
                await ws.send_json({"type": "processing", "text": text})

                loop = asyncio.get_event_loop()
                msgs = conversation.get_messages(system_prompt())
                msgs.append({"role": "user", "content": text})

                def _status(msg: str):
                    asyncio.run_coroutine_threadsafe(
                        ws.send_json({"type": "status", "text": msg}), loop
                    )

                try:
                    response = await loop.run_in_executor(
                        None, lambda: agent.run(msgs, status_callback=_status)
                    )
                except Exception as e:
                    log.error("Agent error: %s", e)
                    response = "Sorry, something went wrong. Please try again."

                conversation.add_user(text)
                conversation.add_assistant(response)
                add_turn("user", text)
                add_turn("assistant", response)
                log.info("Response: %s", response[:80])

                audio = text_to_speech(response)
                if audio:
                    await ws.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio).decode(),
                    })
                    await ws.send_json({
                        "type": "assistant_message",
                        "text": response,
                    })
                else:
                    await ws.send_json({"type": "error", "message": "TTS failed"})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "wake":
                log.info("Manual wake triggered")

    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
        active_ws = None
    except Exception as e:
        log.error("WS error: %s", e)
        active_ws = None

# --- REST ---
class BrowseOpenRequest(BaseModel):
    url: str

class BrowseSearchRequest(BaseModel):
    query: str

class VisionRequest(BaseModel):
    prompt: str = "Describe what you see on the screen."

class WorkspaceLaunchRequest(BaseModel):
    apps: list[str] = []

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/browse/open")
async def browse_open(body: BrowseOpenRequest):
    bt = get_browser()
    try:
        bt.open_url(body.url)
        return {"status": "ok", "url": body.url}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        bt.close()

@app.post("/browse/search")
async def browse_search(body: BrowseSearchRequest):
    bt = get_browser()
    try:
        results = bt.search(body.query)
        return {"status": "ok", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        bt.close()

@app.post("/browse/interact")
async def browse_interact(action: str, selector: str = "", text: str = ""):
    bt = get_browser()
    try:
        if action == "click":
            bt.click(selector)
        elif action == "type":
            bt.type_text(selector, text)
        elif action == "scroll":
            bt.scroll(text or "down")
        elif action == "screenshot":
            img_bytes = bt.take_screenshot()
            path = storeScreenshot(img_bytes, "browse")
            return {"status": "ok", "path": path}
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        bt.close()

@app.post("/vision/describe")
async def vision_describe(body: VisionRequest):
    from vision import describe_screen
    try:
        desc = describe_screen(body.prompt)
        return {"status": "ok", "description": desc}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class ConfigSaveRequest(BaseModel):
    minimax_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    user_name: str = ""
    city: str = ""
    clap_threshold: Optional[float] = None
    clap_max_gap: Optional[float] = None
    keyword_phrase: str = ""
    keyword_enabled: Optional[bool] = None
    ollama_base_url: str = ""
    ollama_model: str = ""
    apps: Optional[list[str]] = None
    response_style: str = ""
    enabled_tools: Optional[list[str]] = None
    system_prompt_override: Optional[str] = None
    elevenlabs_stability: Optional[float] = None
    elevenlabs_similarity_boost: Optional[float] = None

_ALLOW_EMPTY = {"system_prompt_override"}

@app.post("/config/save")
async def save_config(body: ConfigSaveRequest):
    """Save API keys and settings from UI — writes to config.json and hot-reloads."""
    import json
    import config as config_module
    from pathlib import Path
    config_path = Path(__file__).parent / "config.json"

    example_path = Path(__file__).parent / "config.example.json"
    source_path = config_path if config_path.exists() else example_path
    with open(source_path) as f:
        data = json.load(f)

    update_fields = body.model_dump()

    # Handle __clear__ for system_prompt_override before the main loop
    if update_fields.get("system_prompt_override") == "__clear__":
        data["system_prompt_override"] = ""
        del update_fields["system_prompt_override"]

    for key, value in update_fields.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "" and key not in _ALLOW_EMPTY:
            continue
        data[key] = value

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)

    # Hot-reload config in memory — no restart needed
    config_module.reload()

    _SECRET_KEYS = [
        "minimax_api_key", "openai_api_key", "anthropic_api_key",
        "elevenlabs_api_key", "elevenlabs_voice_id",
    ]
    safe_data = dict(data)
    for secret_key in _SECRET_KEYS:
        if safe_data.get(secret_key):
            safe_data[secret_key] = safe_data[secret_key][:8] + "***"

    log.info("Config saved and reloaded from UI")
    return {"status": "ok", "config": safe_data}


_SECRET_KEYS = [
    "minimax_api_key", "openai_api_key", "anthropic_api_key",
    "elevenlabs_api_key", "elevenlabs_voice_id",
]

@app.get("/config")
async def get_config():
    """Return current config (secrets masked)."""
    from config import config as cfg
    safe = dict(cfg)
    for key in _SECRET_KEYS:
        if safe.get(key):
            safe[key] = safe[key][:8] + "***"
    return safe


@app.get("/memory/facts")
async def memory_facts():
    """Return all stored user facts for the memory panel."""
    facts = get_facts()
    return {"status": "ok", "facts": facts}

@app.post("/memory/clear")
async def memory_clear():
    """Delete all stored user facts."""
    clear_facts()
    return {"status": "ok"}

@app.get("/reminders")
async def list_reminders_endpoint():
    from memory import get_upcoming_reminders
    reminders = get_upcoming_reminders()
    return {"status": "ok", "reminders": reminders}

@app.delete("/reminders/{rid}")
async def delete_reminder_endpoint(rid: int):
    from memory import mark_reminder_done
    mark_reminder_done(rid)
    return {"status": "ok"}

class TriggerToggleRequest(BaseModel):
    enabled: bool

@app.post("/triggers/clap")
async def toggle_clap(body: TriggerToggleRequest):
    """Start or stop the clap wake trigger at runtime."""
    if body.enabled:
        if not hasattr(app.state, "clap_trigger") or not app.state.clap_trigger._running:
            try:
                from wake.clap_trigger import ClapTrigger
                trigger = ClapTrigger(
                    threshold=config.get("clap_threshold", 0.15),
                    max_gap=config.get("clap_max_gap", 1.2),
                )
                trigger.set_callback(lambda: _trigger_wake())
                trigger.start()
                app.state.clap_trigger = trigger
                log.info("Clap trigger enabled via API")
            except Exception as e:
                return {"status": "error", "message": str(e)}
    else:
        if hasattr(app.state, "clap_trigger"):
            app.state.clap_trigger.stop()
            del app.state.clap_trigger
            log.info("Clap trigger disabled via API")
    return {"status": "ok", "enabled": body.enabled}

@app.post("/triggers/keyword")
async def toggle_keyword(body: TriggerToggleRequest):
    """Start or stop the keyword wake trigger at runtime."""
    if body.enabled:
        if not hasattr(app.state, "keyword_trigger") or not app.state.keyword_trigger._running:
            try:
                from wake.keyword_trigger import KeywordTrigger
                kw = KeywordTrigger(phrase=config.get("keyword_phrase", "hey assistant"))
                kw.set_callback(lambda: _trigger_wake())
                kw.start()
                app.state.keyword_trigger = kw
                log.info("Keyword trigger enabled via API")
            except Exception as e:
                return {"status": "error", "message": str(e)}
    else:
        if hasattr(app.state, "keyword_trigger"):
            app.state.keyword_trigger.stop()
            del app.state.keyword_trigger
            log.info("Keyword trigger disabled via API")
    return {"status": "ok", "enabled": body.enabled}

@app.post("/workspace/launch")
async def workspace_launch(body: WorkspaceLaunchRequest):
    import subprocess
    from config import config
    apps = body.apps or config.get("apps", [])
    launched = []
    for app in apps:
        try:
            subprocess.Popen(app, shell=True)
            launched.append(app)
        except Exception as e:
            log.error("Failed to launch %s: %s", app, e)
    return {"status": "ok", "launched": launched}

@app.post("/workspace/snap")
async def workspace_snap():
    import subprocess
    import platform
    system = platform.system()
    if system == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File",
                 str(Path(__file__).parent / "scripts" / "snap-windows.ps1")],
                capture_output=True, text=True, timeout=30
            )
            return {"status": "ok", "output": result.stdout}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": f"Unsupported platform: {system}"}

if __name__ == "__main__":
    log.info("Starting Voice Assistant server on :8340")
    uvicorn.run(app, host="0.0.0.0", port=8340, log_level="info")