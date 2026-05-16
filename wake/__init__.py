# Wake module — imports fail gracefully if sounddevice/numpy unavailable
try:
    from .clap_trigger import ClapTrigger
except ImportError:
    ClapTrigger = None

try:
    from .keyword_trigger import KeywordTrigger
except ImportError:
    KeywordTrigger = None

try:
    from .trigger_server import start_trigger_server
except ImportError:
    start_trigger_server = None

__all__ = ["ClapTrigger", "KeywordTrigger", "start_trigger_server"]