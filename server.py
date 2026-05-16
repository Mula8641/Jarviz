"""Voice Assistant server — FastAPI + WebSocket hub."""
import asyncio
import atexit
import base64
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from pathlib import Path
import threading

from config import config
from logger import setup_logger
from audio_tools import text_to_speech
from llm import chat, describe_image
from prompts import system_prompt, greeting_prompt
from context import ConversationContext
from memory import add_turn
from browser_tools import BrowserTools, get_browser
from screenshot_cache import storeScreenshot
from wake.trigger_server import start_trigger_server

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

    yield

    # Shutdown
    if hasattr(app.state, "clap_trigger"):
        app.state.clap_trigger.stop()
    if hasattr(app.state, "keyword_trigger"):
        app.state.keyword_trigger.stop()
    if hasattr(app.state, "stop_trigger"):
        app.state.stop_trigger()

def _trigger_wake():
    global active_ws
    import asyncio
    if active_ws:
        asyncio.create_task(_send_greeting(active_ws))

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
    except Exception:
        pass

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

                text_lower = text.lower()
                if any(k in text_lower for k in ["search for", "search "]):
                    query = text.replace("search for", "").replace("search", "").strip()
                    await ws.send_json({"type": "status", "text": f"Searching: {query}"})
                    bt = get_browser()
                    try:
                        results = bt.search(query)
                        bt.close()
                        response = chat([
                            {"role": "system", "content": "Summarize these search results concisely in 2-3 sentences."},
                            {"role": "user", "content": "\n".join(results)},
                        ])
                    except Exception as e:
                        response = f"Search failed: {e}"
                        bt.close()
                elif any(k in text_lower for k in ["open ", "go to ", "navigate to"]):
                    url = text.split()[-1].strip(".,!?")
                    if not url.startswith("http"):
                        url = "https://" + url
                    await ws.send_json({"type": "status", "text": f"Opening: {url}"})
                    bt = get_browser()
                    try:
                        bt.open_url(url)
                        content = bt.read_page()[:2000]
                        bt.close()
                        response = f"Opened {url}. Page has {len(content)} chars."
                    except Exception as e:
                        response = f"Failed to open {url}: {e}"
                        bt.close()
                else:
                    msgs = conversation.get_messages(system_prompt())
                    msgs.append({"role": "user", "content": text})
                    response = chat(msgs)

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

# --- REST ---
class BrowseOpenRequest(BaseModel):
    url: str

class BrowseSearchRequest(BaseModel):
    query: str

class VisionRequest(BaseModel):
    prompt: str = "Describe what you see on the screen."

class WorkspaceLaunchRequest(BaseModel):
    apps: list[str] = []

@app.get("/")
async def root():
    return {"status": "ok", "service": "voice-assistant"}

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
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    user_name: str = ""
    city: str = ""
    clap_threshold: float = 0.15
    keyword_phrase: str = ""
    keyword_enabled: bool = False

@app.post("/config/save")
async def save_config(body: ConfigSaveRequest):
    """Save API keys and settings from UI — writes to config.json."""
    import json
    from pathlib import Path
    config_path = Path(__file__).parent / "config.json"

    # Load existing or example
    example_path = Path(__file__).parent / "config.example.json"
    with open(example_path) as f:
        data = json.load(f)

    # Update with new values
    update_fields = body.model_dump()
    for key, value in update_fields.items():
        if value != "" and value is not None:
            data[key] = value

    # Mask keys in response
    safe_data = dict(data)
    for secret_key in ["minimax_api_key", "elevenlabs_api_key", "elevenlabs_voice_id"]:
        if safe_data.get(secret_key):
            safe_data[secret_key] = safe_data[secret_key][:8] + "***"

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)

    log.info("Config saved from UI")
    return {"status": "ok", "config": safe_data}


@app.get("/config")
async def get_config():
    """Return current config (secrets masked)."""
    from config import config as cfg
    import copy
    safe = dict(cfg)
    for key in ["minimax_api_key", "elevenlabs_api_key", "elevenlabs_voice_id"]:
        if safe.get(key):
            safe[key] = safe[key][:8] + "***"
    return safe


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