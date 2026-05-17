"""Agent tools — JSON schemas for LLM + executor functions."""
import json
import logging
import subprocess

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
