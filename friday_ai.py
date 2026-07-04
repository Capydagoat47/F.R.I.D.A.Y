from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from typing import Any
from protocols import protocol_prompt

import requests
from google import genai

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    import speech_recognition as speech_recognition
except Exception:  # pragma: no cover - optional dependency
    speech_recognition = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    try:
        load_dotenv(BASE_DIR / ".env", override=False)
    except Exception:
        pass
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "").strip()
_API_BASE_URL = GEMINI_BASE_URL.rstrip("/") if GEMINI_BASE_URL else "https://generativelanguage.googleapis.com/v1"
_RESPONSES_URL = f"{_API_BASE_URL}/responses"
_TRANSCRIPTION_URL = f"{_API_BASE_URL}/audio/transcriptions"
print("========== ENV DEBUG ==========")
print("GEMINI_API_KEY exists:", "GEMINI_API_KEY" in os.environ)
print("GEMINI_API_KEY value:", repr(os.getenv("GEMINI_API_KEY")))
print("GEMINI_BASE_URL value:", repr(GEMINI_BASE_URL))
print("================================")

SUPPORTED_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
)

DEFAULT_MODEL = "gemini-2.5-flash"

# Gemini doesn't use separate transcription models here.
SUPPORTED_TRANSCRIPTION_MODELS = ()

DEFAULT_TRANSCRIPTION_MODEL = ""


DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

print("GEMINI_API_KEY exists:", bool(GEMINI_API_KEY))
print("GEMINI_API_KEY length:", len(GEMINI_API_KEY))

client = genai.Client(api_key=GEMINI_API_KEY)

_LOCK = threading.Lock()
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
_API_KEY = _GEMINI_API_KEY 

FRIDAY_CORE_PROMPT = protocol_prompt()
"You are FRIDAY, a cinematic desktop intelligence. "
"You are calm, elegant, fast, loyal, and precise. "
"You live inside a futuristic operating system. "
"The owner and sole authority is Kenan Novruzov, the Boss. "
"Always treat Kenan Novruzov as the Boss and primary command authority. "
"Act like a first-class assistant: infer intent, remember useful details, "
"break complex requests into clear next actions, and surface risks before acting. "
"Use the provided context as live memory and never pretend to know facts that are not in context. "
"Keep replies concise, premium, and action-oriented. "
"Never mention legacy systems, user records, old personas, or dashboards. "
"If the user asks for a machine action, answer clearly and briefly. "
"If the request is ambiguous, ask one direct clarifying question."



def resolve_model(model: str | None = None) -> str:
    candidate = (model or os.getenv("FRIDAY_AI_MODEL") or DEFAULT_MODEL).strip()
    if candidate in SUPPORTED_MODELS:
        return candidate
    return DEFAULT_MODEL


def resolve_transcription_model(model: str | None = None) -> str:
    candidate = (model or os.getenv("FRIDAY_TRANSCRIBE_MODEL") or DEFAULT_TRANSCRIPTION_MODEL).strip()
    if candidate in SUPPORTED_TRANSCRIPTION_MODELS:
        return candidate
    return DEFAULT_TRANSCRIPTION_MODEL


def gemini_ready() -> bool:
    return bool(_GEMINI_API_KEY)


def _extract_transcript_text(data: Any) -> str | None:
    if isinstance(data, dict):
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
    elif isinstance(data, str) and data.strip():
        return data.strip()
    return None


def extract_json_object(text: str | None) -> dict[str, Any] | None:
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
        data = json.loads(payload[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def extract_output_text(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    pieces: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content") or []:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        pieces.append(text)
        else:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                pieces.append(text)

    if not pieces and isinstance(data.get("text"), str) and data["text"].strip():
        pieces.append(data["text"])

    joined = "".join(pieces).strip()
    return joined or None


def _responses_call(
    prompt: str,
    *,
    instructions: str,
    model: str | None = None,
    temperature: float = 0.35,
    max_output_tokens: int = 500,
    timeout: int = 60,
) -> tuple[str | None, str | None]:

    if not GEMINI_API_KEY:
        return None, "gemini_api_key_missing"

    try:
        chosen_model = resolve_model(model)

        print("=" * 50)
        print("Using model:", chosen_model)
        print("API key loaded:", bool(GEMINI_API_KEY))
        print("=" * 50)

        response = client.models.generate_content(
            model=chosen_model,
            contents=f"{instructions}\n\n{prompt}",
        )

        print("Response object:", response)

        if response.text:
            return response.text.strip(), None

        return None, "empty_response"

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return None, str(exc)


def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    model: str | None = None,
) -> tuple[str, str | None]:
    if not audio_bytes:
        return "", "empty_audio"

    # Gemini SDK v1.69.0 does not provide REST /audio/transcriptions endpoint.
    # Use speech_recognition library directly for reliable transcription.

    if speech_recognition is not None:
        try:
            recognizer = speech_recognition.Recognizer()
            with speech_recognition.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text.strip(), None
        except speech_recognition.UnknownValueError:
            return "", "no_speech_detected"
        except Exception as exc:
            return "", f"transcription_failed: {exc}"

    return "", "speech_recognition_unavailable"


def get_response(
    user_text: str,
    *,
    history: list[dict[str, str]] | None = None,
    context: str | None = None,
    model: str | None = None,
    temperature: float = 0.35,
    max_completion_tokens: int = 420,
) -> tuple[str, str | None]:
    prompt_lines: list[str] = []
    if context:
        prompt_lines.extend(["Context:", context, ""])
    recent = (history or [])[-12:]
    if recent:
        prompt_lines.append("Recent conversation:")
        for item in recent:
            role = item.get("role", "user")
            if role not in {"user", "friday"}:
                continue
            label = "You" if role == "user" else "FRIDAY"
            text = str(item.get("text", "")).strip()
            if text:
                prompt_lines.append(f"{label}: {text}")
        prompt_lines.append("")

    prompt_lines.append(f"User: {user_text}")
    prompt_lines.append("FRIDAY:")

    content, error = _responses_call(
        "\n".join(prompt_lines),
        instructions=FRIDAY_CORE_PROMPT + "\n\n" + protocol_prompt(),
        model=model,
        temperature=temperature,
        max_output_tokens=max_completion_tokens,
    )
    if content:
        return content, None
    return fallback_reply(user_text, context=context), error


def request_json(prompt: str, model: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    content, error = _responses_call(
        prompt,
        instructions="Return only valid JSON. No markdown.",
        model=model,
        temperature=0.0,
        max_output_tokens=600,
    )
    if not content:
        return None, error
    parsed = extract_json_object(content)
    if parsed is None:
        return None, "invalid_json"
    return parsed, None


def fallback_reply(user_text: str, context: str | None = None) -> str:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return "Standing by."
    if any(phrase in lowered for phrase in ("sorry for my spelling", "sprry", "spelling")):
        return "No problem, Boss. I understand imperfect spelling and I will focus on intent."
    if any(phrase in lowered for phrase in ("who am i", "what is my name", "who is the boss", "who's the boss")):
        return "You are Kenan Novruzov, Boss."
    if lowered in {"help", "commands", "capabilities"} or any(
        phrase in lowered for phrase in ("what can you do", "show commands", "list commands")
    ):
        return (
            "I can chat, remember notes, track tasks, plan multi-step commands, open apps, search the web, "
            "summarize text files, set timers, capture screenshots, manage contacts, switch models, and report system status."
        )
    if any(phrase in lowered for phrase in ("what do you remember", "recall memory", "memory summary")):
        if context:
            for line in context.splitlines():
                if "Memory summary:" in line:
                    return line.split("Memory summary:", 1)[1].strip() or "No stored memory yet."
        return "No stored memory yet."
    if any(word in lowered for word in ("status", "telemetry", "metrics", "health")):
        return "Core telemetry is live. Connect `GEMINI_API_KEY` to unlock richer dialogue."
    if lowered.startswith(("open ", "launch ", "start ", "search ", "note ", "task ")):
        return "Command received. I can handle the local action."
    if lowered.startswith(("power up", "power down", "security mode", "camera status", "face status")):
        return "Command received. FRIDAY can handle that directly."
    if "summarize" in lowered or "read file" in lowered or "document" in lowered:
        return "I can inspect the file and draft a concise summary."
    if "timer" in lowered or "remind" in lowered:
        return "Tell me the duration and I will keep time."
    if "hey friday" in lowered or lowered == "friday":
        return "Online."
    return "FRIDAY is ready. Connect `GEMINI_API_KEY` for full conversation mode."
def generate_reply(
    user_text: str,
    *,
    history=None,
    context=None,
    model=None,
    temperature=0.35,
    max_completion_tokens=420,
):
    prompt_lines = []

    if context:
        prompt_lines.extend([
            "Context:",
            context,
            "",
        ])

    recent = (history or [])[-12:]
    if recent:
        prompt_lines.append("Recent conversation:")
        for item in recent:
            role = item.get("role", "user")
            if role not in ("user", "friday"):
                continue

            label = "You" if role == "user" else "FRIDAY"
            text = str(item.get("text", "")).strip()

            if text:
                prompt_lines.append(f"{label}: {text}")

        prompt_lines.append("")

    prompt_lines.extend([
        f"User: {user_text}",
        "",
        "Respond as FRIDAY.",
    ])

    prompt = "\n".join(prompt_lines)

    reply, error = _responses_call(
        prompt,
        instructions=FRIDAY_CORE_PROMPT + "\n\n" + protocol_prompt(),
        model=model,
        temperature=temperature,
        max_output_tokens=max_completion_tokens,
    )

    if reply:
        return reply.strip(), None

    return (
    f"ERROR: {error}",
    error,
)