import json
import os
import tempfile
from datetime import datetime

import requests

# speech_recognition depends on the stdlib module `aifc` which is not available in some minimal
# Python builds. Import lazily inside listen_and_transcribe() so the web UI can still run.
sr = None

from gtts import gTTS




class SpeechIO:
    def __init__(self, config: dict):
        self.config = config
        self.sample_rate = (config.get("audio") or {}).get("sample_rate", 16000)
        self.record_seconds = (config.get("audio") or {}).get("record_seconds", 6)
        self.stt_language = (config.get("audio") or {}).get("stt_language", "en-US")

        self.openai = (config.get("cloud") or {}).get("openai") or {}
        self.api_key = self.openai.get("api_key")
        self.model = self.openai.get("model", "gpt-4o-mini")

    def listen_and_transcribe(self) -> str:
        # Simple + reliable: use microphone capture + Google Web Speech via SpeechRecognition.
        global sr
        if sr is None:
            import speech_recognition as _sr

            sr = _sr

        r = sr.Recognizer()
        mic = sr.Microphone()


        with mic as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=self.record_seconds + 2, phrase_time_limit=self.record_seconds)

        text = r.recognize_google(audio, language=self.stt_language)
        return text

    def speak(self, text: str):
        # Simple + reliable: gTTS (cloud). For offline TTS you'd swap to espeak-ng/cepstral.
        text = text.strip()
        if not text:
            return

        tmp_dir = tempfile.gettempdir()
        fname = os.path.join(tmp_dir, f"forte_tts_{int(datetime.now().timestamp())}.mp3")

        tts = gTTS(text=text, lang=self.stt_language.split("-")[0])
        tts.save(fname)
        # Playback strategy:
        # - Convert MP3 -> WAV with ffmpeg (required)
        # - Play WAV using OS-appropriate command
        #   * Linux/Raspberry Pi: `aplay` (from alsa-utils)
        #   * Windows: `os.startfile`
        #   * macOS: `afplay`
        try:
            import pathlib
            import subprocess
            import sys
            from shutil import which

            if which('ffmpeg') is None:
                raise RuntimeError("ffmpeg not found. Install it with: sudo apt install ffmpeg")

            wav = str(pathlib.Path(fname).with_suffix('.wav'))
            subprocess.check_call(
                ['ffmpeg', '-y', '-i', fname, wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if sys.platform.startswith('win'):
                os.startfile(wav)
            elif sys.platform == 'darwin':
                subprocess.check_call(['afplay', wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Assume Linux
                if which('aplay') is None:
                    raise RuntimeError("aplay not found. Install it with: sudo apt install alsa-utils")
                subprocess.check_call(['aplay', '-q', wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            raise RuntimeError(f"TTS playback failed: {e}. Install ffmpeg and a working audio output device.")



    def llm_answer(self, user_text: str) -> str:
        # OpenAI Responses API (kept simple)
        if not self.api_key or self.api_key == "REPLACE_ME":
            # If no key is set, return a safe local response.
            return f"You said: '{user_text}'. (OpenAI API key not configured.)"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            "You are Forte, an assistant that helps a person in their room. "
            "Be concise, practical, and action-oriented. "
            "If the user asks for something unclear, ask a short follow-up.\n\n"
            f"User said: {user_text}\n\nForte:"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are Forte."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        }

        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "Done.")

