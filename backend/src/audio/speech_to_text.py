from __future__ import annotations

import contextlib
import os
from typing import Optional


class SpeechToText:
    def __init__(self, energy_threshold: int = 300, pause_threshold: float = 0.8):
        # Lazy import so environments without SpeechRecognition can still run (--no-audio)
        try:
            import speech_recognition as sr  # type: ignore
            self._sr = sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = energy_threshold
            self.recognizer.pause_threshold = pause_threshold
        except Exception:
            # No speech recognition available
            self._sr = None
            self.recognizer = None  # type: ignore

    def listen(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
        """Listen from the default microphone and return recognized text using Google Web Speech API.

        Headless mode: If env var INTERVIEW_HEADLESS is set, return a canned answer without using the mic.
        """
        if os.getenv("INTERVIEW_HEADLESS"):
            return "[headless] This is a stubbed answer."

        if not self._sr or not self.recognizer:
            return ""
        with contextlib.ExitStack() as stack:
            mic = stack.enter_context(self._sr.Microphone())
            self.recognizer.adjust_for_ambient_noise(mic, duration=0.5)
            audio = self.recognizer.listen(mic, timeout=timeout, phrase_time_limit=phrase_time_limit)
        try:
            return self.recognizer.recognize_google(audio)
        except Exception:
            return ""

    def transcribe_file(self, wav_path: str) -> str:
        """Transcribe from a WAV file as a fallback/testing path."""
        if not self._sr or not self.recognizer:
            return ""
        with self._sr.AudioFile(wav_path) as source:
            audio = self.recognizer.record(source)
        try:
            return self.recognizer.recognize_google(audio)
        except Exception:
            return ""
