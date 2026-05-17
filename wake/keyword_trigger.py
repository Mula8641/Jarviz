"""Keyword wake trigger — detects configurable phrase from audio stream.

Gracefully skips if sounddevice not available.
Requires SpeechRecognition for actual phrase matching; falls back to
energy-only detection if that library is missing.
"""
try:
    import numpy as np
    import sounddevice as sd
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False
    np = None
    sd = None

try:
    import speech_recognition as sr
    _HAS_SR = True
except ImportError:
    _HAS_SR = False
    sr = None

import threading
import logging
import time

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
        self.phrase = phrase.lower()
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
        self._recognizer = sr.Recognizer() if _HAS_SR else None

        if not _HAS_SR:
            log.warning(
                "SpeechRecognition not installed — keyword trigger will fire on any speech. "
                "Install it: pip install SpeechRecognition"
            )

    def set_callback(self, fn):
        self.callback = fn

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Keyword trigger started — phrase: '%s'", self.phrase)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("Keyword trigger stopped")

    def _listen_loop(self):
        in_speech = False
        speech_start = 0.0
        buffer = []

        def audio_callback(indata, frames, time_info, status):
            nonlocal in_speech, speech_start, buffer
            if status:
                return

            audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()
            rms = float(np.sqrt(np.mean(audio ** 2)))
            now = time.time()

            if rms > self.energy_threshold:
                if not in_speech:
                    in_speech = True
                    speech_start = now
                    buffer = [audio.copy()]
                else:
                    buffer.append(audio.copy())
            else:
                if in_speech:
                    duration = now - speech_start
                    if duration >= self.min_phrase_len:
                        self._process_buffer(buffer[:])
                    buffer = []
                    in_speech = False

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_samples,
            channels=1,
            dtype="float32",
            callback=audio_callback,
        )
        with stream:
            while self._running:
                sd.sleep(200)

    def _process_buffer(self, buffer):
        now = time.time()
        if now - self._last_trigger < self.cooldown:
            return

        if _HAS_SR and self._recognizer:
            try:
                audio_data = np.concatenate(buffer)
                # Convert float32 [-1, 1] → int16 PCM bytes
                pcm = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                audio_segment = sr.AudioData(pcm, self.sample_rate, 2)
                text = self._recognizer.recognize_google(audio_segment).lower()
                log.debug("Heard: '%s'", text)
                if self.phrase in text:
                    log.info("Keyword '%s' detected in: '%s'", self.phrase, text)
                    self._last_trigger = now
                    if self.callback:
                        self.callback()
            except sr.UnknownValueError:
                pass  # Speech not understood — not the keyword
            except sr.RequestError as e:
                log.warning("STT service error: %s", e)
            except Exception as e:
                log.debug("Keyword process error: %s", e)
        else:
            # Energy-only fallback: fire on any sustained speech
            log.info("Keyword trigger fired (energy-only mode — install SpeechRecognition for phrase matching)")
            self._last_trigger = now
            if self.callback:
                self.callback()

    def update_phrase(self, phrase: str):
        self.phrase = phrase.lower()
        log.info("Keyword phrase updated: '%s'", self.phrase)
