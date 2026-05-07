import json
import os
import threading
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    import google.genai as google_genai
except Exception:
    google_genai = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    try:
        load_dotenv(BASE_DIR / ".env", override=False)
    except Exception:
        pass

DEFAULT_MODEL = os.getenv("FRIDAY_AI_MODEL", "gemini-2.5-flash")
_CLIENT = None
_CLIENT_LOCK = threading.Lock()


def ai_enabled():
    return google_genai is not None and bool(os.getenv("GEMINI_API_KEY"))


def get_client():
    global _CLIENT
    if not ai_enabled():
        return None
    if _CLIENT is not None:
        return _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _CLIENT


def extract_json_object(text):
    if not text:
        return None
    payload = text.strip()
    if payload.startswith("```"):
        parts = payload.split("```")
        if len(parts) >= 3:
            payload = parts[1]
            if payload.startswith("json"):
                payload = payload[4:]
        payload = payload.strip()
    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(payload[start : end + 1])
    except json.JSONDecodeError:
        return None


def request_json(prompt, model=None):
    client = get_client()
    if client is None:
        return None, "ai_unavailable"
    try:
        response = client.models.generate_content(
            model=model or DEFAULT_MODEL,
            contents=prompt,
        )
        text = getattr(response, "text", "") or ""
        data = extract_json_object(text)
        if data is None:
            return None, "invalid_json"
        return data, None
    except Exception as exc:
        return None, str(exc)
