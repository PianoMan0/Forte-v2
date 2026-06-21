import json
import os
import threading

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

try:
    # When run as `python -m forte.app`
    from .assistant.engine import Assistant
except ImportError:
    # When run as a script: `python forte/app.py`
    from assistant.engine import Assistant


def load_config():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(here, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # fallback to example
    example_path = os.path.join(here, "config.example.json")
    with open(example_path, "r", encoding="utf-8") as f:
        return json.load(f)


app = Flask(
    __name__,
    template_folder="dashboard/templates",
    static_folder="dashboard/static",
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

assistant = Assistant(config=load_config())


@app.get("/")
def index():
    return render_template("index.html", name=assistant.name)


@socketio.on("connect")
def on_connect():
    emit("status", {"state": "ready"})


@socketio.on("listen")
def on_listen(_payload=None):
    # Important: don't use `emit()` from a background thread without the
    # request context. Emit from the socket handler thread instead.
    emit("status", {"state": "listening"})
    try:
        transcript = assistant.record_and_transcribe()
        emit("transcript", {"text": transcript})
        emit("status", {"state": "thinking"})
        response_text = assistant.chat(transcript)
        emit("response", {"text": response_text})
        emit("status", {"state": "speaking"})
        assistant.speech.speak(response_text)
        emit("status", {"state": "ready"})
    except Exception as e:
        emit("error", {"message": str(e)})
        emit("status", {"state": "ready"})


@socketio.on("quick_action")
def on_quick_action(data):
    action = (data or {}).get("action")
    emit("status", {"state": "thinking"})
    try:
        response_text = assistant.quick_action(action)
        emit("response", {"text": response_text})
        assistant.speech.speak(response_text)
        emit("status", {"state": "ready"})
    except Exception as e:
        emit("error", {"message": str(e)})
        emit("status", {"state": "ready"})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

