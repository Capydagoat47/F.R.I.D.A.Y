from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    try:
        load_dotenv(BASE_DIR / ".env", override=False)
    except Exception:
        pass

SUPPORTED_MODELS = ("gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4o")
DEFAULT_MODEL = "gpt-5"

_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
_RESPONSES_URL = f"{_BASE_URL}/responses"
_LOCK = threading.Lock()

FRIDAY_CORE_PROMPT = (
    "You are FRIDAY, a cinematic desktop intelligence. "
    "You are calm, elegant, fast, loyal, and precise. "
    "You live inside a futuristic operating system. "
    "Keep replies concise, premium, and action-oriented. "
    "Never mention legacy systems, user records, old personas, or dashboards. "
    "If the user asks for a machine action, answer clearly and briefly. "
    "If the request is ambiguous, ask one direct clarifying question."
)


def resolve_model(model: str | None = None) -> str:
    candidate = (model or os.getenv("FRIDAY_AI_MODEL") or DEFAULT_MODEL).strip()
    if candidate in SUPPORTED_MODELS:
        return candidate
    return DEFAULT_MODEL


def openai_ready() -> bool:
    return bool(_API_KEY)


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
    if not _API_KEY:
        return None, "openai_api_key_missing"

    payload: dict[str, Any] = {
        "model": resolve_model(model),
        "instructions": instructions,
        "input": prompt,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }

    try:
        with _LOCK:
            response = requests.post(
                _RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
    except requests.RequestException as exc:
        return None, str(exc)

    if not response.ok:
        return None, f"http_{response.status_code}: {response.text[:300]}"

    try:
        data = response.json()
    except ValueError:
        return None, "invalid_json_response"

    content = extract_output_text(data)
    if not content:
        return None, "missing_content"
    return content, None


def generate_reply(
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
    prompt_lines.extend(
        [
            "User request:",
            user_text,
            "",
            "Reply as FRIDAY. Keep the response concise, cinematic, and action-oriented.",
        ]
    )

    content, error = _responses_call(
        "\n".join(prompt_lines),
        instructions=FRIDAY_CORE_PROMPT,
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
    if any(word in lowered for word in ("status", "telemetry", "metrics", "health")):
        return "Core telemetry is live. Connect `OPENAI_API_KEY` to unlock richer dialogue."
    if lowered.startswith(("open ", "launch ", "start ", "search ", "note ", "task ")):
        return "Command received. I can handle the local action."
    if "summarize" in lowered or "read file" in lowered or "document" in lowered:
        return "I can inspect the file and draft a concise summary."
    if "timer" in lowered or "remind" in lowered:
        return "Tell me the duration and I will keep time."
    if "hey friday" in lowered or lowered == "friday":
        return "Online."
    return "FRIDAY is ready. Connect `OPENAI_API_KEY` for full conversation mode."
