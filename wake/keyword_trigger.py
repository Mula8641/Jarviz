"""Keyword wake trigger — detects configurable phrase from audio stream.

Gracefully skips if sounddevice not available (no Windows wheel).
Use mic button or keyword wake as primary trigger.
"""
try:
    import numpy as np
    import sounddevice as sd
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False
    np = None
    sd = None

import threading
import logging
import queue
import json

from config import config

log = logging.getLogger("keyword")

class KeywordTrigger:
    def __init__(
        self,
        phrase: str = "hey assistant",
        sample_rate: int = 16000,
        chunk_ms: int = 100,
        energy_threshold: float = 0.02,
        min_phrase_len: float = 0.5,
        cooldown: float = 3.0,
    ):
        if not _HAS_AUDIO:
            raise ImportError("sounddevice not available")
        self.phrase = phrase.lower().split()
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.chunk_samples = int(sample_rate * chunk_ms / 1000)
        self.energy_threshold = energy_threshold
        self.min_phrase_len = min_phrase_len
        self.cooldown = cooldown

        self.callback = None
        self._running = False
        self._thread = None
        self._last_trigger = 0.0
        self._audio_buffer = []

    def set_callback(self, fn):
        self.callback = fn

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Keyword trigger started — phrase: '%s'", " ".join(self.phrase))

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("Keyword trigger stopped")

    def _listen_loop(self):
        in_speech = False
        speech_start = 0
        buffer = []

        def callback(indata, frames, time_info, status):
            nonlocal in_speech, speech_start, buffer
            if status:
                return

            audio = indata[:, 0] if indata.ndim > 1 else indata
            rms = np.sqrt(np.mean(audio ** 2))
            energy = float(rms)
            now = time.time()

            if energy > self.energy_threshold:
                if not in_speech:
                    in_speech = True
                    speech_start = now
                    buffer = [audio]
                else:
                    buffer.append(audio)
            else:
                if in_speech:
                    duration = now - speech_start
                    if duration >= self.min_phrase_len:
                        self._process_buffer(buffer)
                    buffer = []
                    in_speech = False

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_samples,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        with stream:
            while self._running:
                sd.sleep(200)

    def _process_buffer(self, buffer):
        import time
        now = time.time()
        if now - self._last_trigger < self.cooldown:
            return
        log.info("Speech detected, checking keyword...")
        self._last_trigger = now
        if self.callback:
            self.callback()

    def update_phrase(self, phrase: str):
        self.phrase = phrase.lower().split()
        log.info("Keyword phrase updated: %s", phrase)