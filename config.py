"""Config loader — env vars win over JSON."""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).parent / "config.json"
_example = Path(__file__).parent / "config.example.json"

def load():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    else:
        with open(_example) as f:
            data = json.load(f)
    # Env overrides
    data["minimax_api_key"] = os.getenv("MINIMAX_API_KEY", data.get("minimax_api_key", ""))
    data["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY", data.get("elevenlabs_api_key", ""))
    data["elevenlabs_voice_id"] = os.getenv("ELEVENLABS_VOICE_ID", data.get("elevenlabs_voice_id", ""))
    data["user_name"] = os.getenv("USER_NAME", data.get("user_name", "User"))
    data["city"] = os.getenv("CITY", data.get("city", "Berlin"))
    data["clap_threshold"] = float(os.getenv("CLAP_THRESHOLD", data.get("clap_threshold", 0.15)))
    data["clap_max_gap"] = float(os.getenv("CLAP_MAX_GAP", data.get("clap_max_gap", 1.2)))
    data["keyword_phrase"] = os.getenv("KEYWORD_PHRASE", data.get("keyword_phrase", "hey assistant"))
    data["keyword_enabled"] = os.getenv("KEYWORD_ENABLED", str(data.get("keyword_enabled", False))).lower() in ("true", "1", "yes")
    return data

config = load()