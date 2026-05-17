"""Agent tools — JSON schemas for LLM + executor functions."""
import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
import httpx

log = logging.getLogger("tools")

# ── Tool Definitions (OpenAI function-calling schema) ─────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for any topic and return relevant results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the browser and return a preview of the page content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL (https://...)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_screen",
            "description": "Take a screenshot and describe what is currently on the user's screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What specifically to look for or describe",
                        "default": "Describe what you see on the screen in detail.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_facts",
            "description": "Retrieve stored facts about the user from persistent memory.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store an important fact about the user in persistent memory for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Fact identifier (e.g. 'favorite_color')"},
                    "value": {"type": "string", "description": "Fact value (e.g. 'blue')"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Launch an application on the user's computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Application name or shell command to launch"},
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_page_content",
            "description": "Read the text content of the currently open browser page.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city. If no city is given, uses the user's configured city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name (e.g. 'London', 'Berlin')"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remind_me",
            "description": "Set a reminder that Jarviz will speak aloud at the specified time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind the user about"},
                    "when": {
                        "type": "string",
                        "description": (
                            "When to trigger. Natural language: 'in 10 minutes', 'in 2 hours', "
                            "'at 3pm', 'at 14:30', 'tomorrow at 9am'"
                        ),
                    },
                },
                "required": ["message", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all upcoming (pending) reminders.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the current contents of the system clipboard.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_clipboard",
            "description": "Write text to the system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to copy to clipboard"},
                },
                "required": ["text"],
            },
        },
    },
]


# ── Executor ──────────────────────────────────────────────────────────────────

def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name. Returns result as a plain string."""
    log.info("Executing tool: %s(%s)", name, arguments)
    try:
        if name == "search_web":
            return _search_web(**arguments)
        if name == "open_url":
            return _open_url(**arguments)
        if name == "describe_screen":
            return _describe_screen(**arguments)
        if name == "get_memory_facts":
            return _get_memory_facts()
        if name == "remember_fact":
            return _remember_fact(**arguments)
        if name == "launch_app":
            return _launch_app(**arguments)
        if name == "read_page_content":
            return _read_page_content()
        if name == "get_weather":
            return _get_weather(**arguments)
        if name == "remind_me":
            return _remind_me(**arguments)
        if name == "list_reminders":
            return _list_reminders()
        if name == "read_clipboard":
            return _read_clipboard()
        if name == "write_clipboard":
            return _write_clipboard(**arguments)
        return f"Unknown tool: {name}"
    except TypeError as e:
        log.error("Tool %s bad arguments %s: %s", name, arguments, e)
        return f"Tool {name} received invalid arguments: {e}"
    except Exception as e:
        log.error("Tool %s failed: %s", name, e)
        return f"Tool {name} failed: {e}"


# ── Implementations ────────────────────────────────────────────────────────────

def _search_web(query: str) -> str:
    from browser_tools import get_browser
    bt = get_browser()
    results = bt.search(query)
    if not results:
        return "No results found."
    return "\n".join(results[:6])


def _open_url(url: str) -> str:
    from browser_tools import get_browser
    if not url.startswith("http"):
        url = "https://" + url
    bt = get_browser()
    bt.open_url(url)
    content = bt.read_page()[:2000]
    return f"Opened {url}.\n\n{content}"


def _describe_screen(prompt: str = "Describe what you see on the screen in detail.") -> str:
    from vision import describe_screen
    return describe_screen(prompt)


def _get_memory_facts() -> str:
    from memory import get_facts
    facts = get_facts()
    if not facts:
        return "No facts stored yet."
    return "\n".join(f"{k}: {v}" for k, v in facts.items())


def _remember_fact(key: str, value: str) -> str:
    from memory import set_fact
    set_fact(key, str(value))
    return f"Remembered: {key} = {value}"


def _launch_app(app: str) -> str:
    try:
        subprocess.Popen(app, shell=True)
        return f"Launched: {app}"
    except Exception as e:
        return f"Failed to launch '{app}': {e}"


def _read_page_content() -> str:
    from browser_tools import get_browser
    bt = get_browser()
    content = bt.read_page()
    return content[:3000] if content else "No page loaded or page is empty."


def _get_weather(city: str = "") -> str:
    from config import config
    target = (city or config.get("city", "London")).strip()
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"https://wttr.in/{target}?format=j1")
            resp.raise_for_status()
            data = resp.json()
        cur = data["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp_c = cur["temp_C"]
        temp_f = cur["temp_F"]
        feels_c = cur["FeelsLikeC"]
        humidity = cur["humidity"]
        wind = cur["windspeedKmph"]
        return (
            f"Weather in {target}: {desc}, {temp_c}°C ({temp_f}°F). "
            f"Feels like {feels_c}°C. Humidity {humidity}%, wind {wind} km/h."
        )
    except Exception as e:
        return f"Could not get weather for '{target}': {e}"


def _parse_reminder_time(when: str) -> datetime:
    """Parse natural-language time expressions into a UTC datetime."""
    s = when.lower().strip()
    now = datetime.utcnow()

    # "in X seconds" (useful for tests / quick demos)
    m = re.match(r"in (\d+)\s*seconds?", s)
    if m:
        return now + timedelta(seconds=int(m.group(1)))

    # "in X minutes"
    m = re.match(r"in (\d+)\s*(?:minute|minutes|min|mins?)", s)
    if m:
        return now + timedelta(minutes=int(m.group(1)))

    # "in X hours"
    m = re.match(r"in (\d+)\s*(?:hour|hours|hr|hrs?)", s)
    if m:
        return now + timedelta(hours=int(m.group(1)))

    # "tomorrow[ at H[:MM][ am/pm]]"
    m = re.match(r"tomorrow(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", s)
    if m:
        hour = int(m.group(1)) if m.group(1) else 9
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        base = now + timedelta(days=1)
        return base.replace(hour=min(hour, 23), minute=min(minute, 59), second=0, microsecond=0)

    # "at H[:MM][ am/pm]"
    m = re.match(r"at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=min(hour, 23), minute=min(minute, 59), second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    raise ValueError(f"Cannot parse time expression: '{when}'")


def _remind_me(message: str, when: str) -> str:
    try:
        remind_at = _parse_reminder_time(when)
    except ValueError as e:
        return str(e)
    from memory import add_reminder
    rid = add_reminder(message, remind_at.isoformat())
    local_label = remind_at.strftime("%H:%M UTC")
    return f"Reminder #{rid} set: '{message}' at {local_label}."


def _list_reminders() -> str:
    from memory import get_upcoming_reminders
    upcoming = get_upcoming_reminders()
    if not upcoming:
        return "No upcoming reminders."
    lines = []
    for r in upcoming:
        dt = r["remind_at"].replace("T", " ")[:16]
        lines.append(f"• [{r['id']}] {r['message']} — at {dt} UTC")
    return "\n".join(lines)


def _read_clipboard() -> str:
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty."
        return f"Clipboard contents:\n{text[:2000]}"
    except Exception as e:
        return f"Could not read clipboard: {e}"


def _write_clipboard(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        preview = text[:80] + ("..." if len(text) > 80 else "")
        return f"Copied to clipboard: {preview}"
    except Exception as e:
        return f"Could not write to clipboard: {e}"
