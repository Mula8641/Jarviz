"""UDP trigger server — fires wake event from external sources."""
import socket
import logging
import threading
import json

log = logging.getLogger("trigger_server")

def start_trigger_server(port: int = 8341, callback=None):
    """Listens for UDP wake signals and calls callback on receipt."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(1.0)  # allow periodic check of _running flag
    log.info("Trigger server listening on UDP :%d", port)

    running = [True]

    def loop():
        while running[0]:
            try:
                data, addr = sock.recvfrom(256)
                msg = data.decode().strip()
                log.info("Wake signal from %s: %s", addr, msg)
                if callback:
                    callback(msg)
            except socket.timeout:
                continue

    def stop():
        running[0] = False

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return stop

def send_wake(host: str = "127.0.0.1", port: int = 8341, message: str = "wake"):
    """Send a wake signal to the trigger server (e.g. from clap_trigger.py via subprocess)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message.encode(), (host, port))
        sock.close()
    except Exception as e:
        log.error("Failed to send wake signal: %s", e)