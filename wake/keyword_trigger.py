"""Keyword wake trigger — detects configurable phrase from audio stream."""
import numpy as np
import sounddevice as sd
import threading
import logging
import queue
import json

from config import config

log = logging.getLogger("keyword")

# Simple energy-based keyword detection
# For production: swap to Silero VAD for better accuracy
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

            # Convert to mono float
            if indata.ndim > 1:
                audio = indata[:, 0]
            else:
                audio = indata

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

        # Simple: check if phrase words appear in energy peaks pattern
        # Real implementation would use ASR — this is a placeholder
        # that fires on any speech above threshold (for testing)
        log.info("Speech detected, checking keyword...")
        self._last_trigger = now
        if self.callback:
            self.callback()

    def update_phrase(self, phrase: str):
        self.phrase = phrase.lower().split()
        log.info("Keyword phrase updated: %s", phrase)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trigger = KeywordTrigger(
        phrase=config.get("keyword_phrase", "hey assistant"),
    )
    trigger.set_callback(lambda: log.info("🔔 KEYWORD DETECTED"))
    trigger.start()
    log.info("Listening for keyword... Press Ctrl+C to stop")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        trigger.stop()