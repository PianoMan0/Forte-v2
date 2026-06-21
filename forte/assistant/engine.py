import re

from .speech import SpeechIO



class Assistant:
    def __init__(self, config: dict):
        self.config = config
        self.name = (config.get("ui") or {}).get("name", "Forte")
        self.speech = SpeechIO(config=config)

    def record_and_transcribe(self) -> str:
        return self.speech.listen_and_transcribe()

    def chat(self, user_text: str) -> str:
        text = (user_text or "").strip()
        if not text:
            return "I didn't catch that. Try again."

        # Lightweight local routing first for reliability
        t = text.lower()
        if "time" in t:
            return self.quick_action("time")
        if "date" in t:
            return self.quick_action("date")
        if "help" in t or "what can you do" in t:
            return (
                "I can listen to your voice, answer questions, and run quick actions like time and date. "
                "Try saying: 'what time is it' or 'help'."
            )

        # If using OpenAI, keep prompt tight.
        return self.speech.llm_answer(text)

    def quick_action(self, action: str) -> str:
        import datetime

        if action == "time":
            return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}."
        if action == "date":
            return f"Today's date is {datetime.datetime.now().strftime('%A, %B %d, %Y')}."

        # Fallback
        return "Done."

