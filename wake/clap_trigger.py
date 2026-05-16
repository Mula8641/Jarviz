"""Double-clap wake trigger — sounddevice + numpy.

Gracefully skips if sounddevice not available (Windows wheels sometimes unavailable).
Mic button or keyword wake can be used as primary trigger.
"""
try:
    import numpy as np
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False
    np = None
    sd = None

import threading
import logging
import time

from config import config

log = logging.getLogger("clap")


class ClapTrigger:
    def __init__(
        self,
        threshold: float = 0.15,
        max_gap: float = 1.2,
        sample_rate: int = 44100,
        chunk_size: int = 1024,
    ):
        if not _HAS_SOUNDDEVICE:
            raise ImportError("sounddevice not available — install from https://github.com/spatialaudio/python-sounddevice/releases")
        self.threshold = threshold
        self.max_gap = max_gap
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.callback = None
        self._running = False
        self._thread = None

    def set_callback(self, fn):
        self.callback = fn

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Clap trigger started — threshold=%.2f, max_gap=%.1fs", self.threshold, self.max_gap)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        log.info("Clap trigger stopped")

    def _listen_loop(self):
        in_clap = False
        clap_times = []
        silence_start = None

        def callback(indata, frames, time_info, status):
            nonlocal in_clap, silence_start
            if status:
                return
            rms = np.sqrt(np.mean(indata ** 2))
            volume = rms[0] if indata.ndim > 1 else rms

            if volume > self.threshold:
                now = time.time()
                if not in_clap:
                    in_clap = True
                    clap_times = [now]
                    silence_start = None
                else:
                    if clap_times:
                        gap = now - clap_times[-1]
                        if gap <= self.max_gap:
                            clap_times.append(now)
                        else:
                            clap_times = [now]
                silence_start = None
            else:
                if in_clap and clap_times:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > 0.3:
                        if len(clap_times) >= 2:
                            gaps = [clap_times[i+1] - clap_times[i] for i in range(len(clap_times)-1)]
                            avg_gap = sum(gaps) / len(gaps)
                            if avg_gap < 0.6 and all(g < self.max_gap for g in gaps):
                                log.info("Double-clap detected (%d claps)", len(clap_times))
                                if self.callback:
                                    self.callback()
                        clap_times = []
                        in_clap = False

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            channels=1,
            callback=callback,
        )
        with stream:
            while self._running:
                sd.sleep(200)

    def update_threshold(self, value: float):
        self.threshold = value
        log.info("Clap threshold updated to %.2f", value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trigger = ClapTrigger(
        threshold=config.get("clap_threshold", 0.15),
        max_gap=config.get("clap_max_gap", 1.2),
    )
    trigger.set_callback(lambda: log.info("WAKE DETECTED"))
    trigger.start()
    log.info("Listening for double-clap... Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        trigger.stop()