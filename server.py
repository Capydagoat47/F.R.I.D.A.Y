from __future__ import annotations

import base64
import ast
import json
import math
import os
import re
import subprocess
import threading
import time
import webbrowser
import zipfile
from copy import deepcopy
from datetime import datetime
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

from friday_ai import DEFAULT_MODEL, SUPPORTED_MODELS, generate_reply, openai_ready, request_json, resolve_model, transcribe_audio_bytes

HOST = os.getenv("FRIDAY_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
LOCAL_URL = f"http://127.0.0.1:{PORT}"
AUTO_OPEN_BROWSER = os.getenv("FRIDAY_AUTO_OPEN", "1").lower() not in {"0", "false", "no"}

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "friday_state.json"
INDEX_FILE = BASE_DIR / "index.html"
STYLE_FILE = BASE_DIR / "app.css"
SCRIPT_FILE = BASE_DIR / "app.js"
JOURNAL_NAMES_FILE = Path(
    os.getenv(
        "FRIDAY_JOURNAL_NAMES_FILE",
        r"C:\Users\forho\Downloads\4Ə SUMMATİV QİYMETLERİ\IKINCI YARIM IL\Jurnal Sırası — копия.xlsx",
    )
)
JOURNAL_NAMES_DIR = Path(
    os.getenv(
        "FRIDAY_JOURNAL_NAMES_DIR",
        r"C:\Users\forho\Downloads\4Ə SUMMATİV QİYMETLERİ\IKINCI YARIM IL",
    )
)

STATE_LOCK = threading.Lock()
METRICS_LOCK = threading.Lock()
METRICS_CACHE: dict[str, Any] = {"timestamp": 0.0, "data": {}}
STATE: dict[str, Any] = {}

MAX_HISTORY = 40
MAX_EVENTS = 20
MAX_NOTES = 24
MAX_TASKS = 24
MAX_COMMAND_MEMORY = 20
MAX_FACTS = 40

OWNER_NAME = "Kenan Novruzov"
OWNER_TITLE = "Boss"

APP_ALIASES = {
    "calculator": "calc",
    "calc": "calc",
    "notepad": "notepad",
    "paint": "mspaint",
    "terminal": "wt",
    "command prompt": "cmd",
    "file explorer": "explorer",
    "explorer": "explorer",
    "browser": "https://www.google.com",
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "steam": "steam://open/main",
}

MODEL_LOOKUP = sorted(SUPPORTED_MODELS, key=len, reverse=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{os.getpid()}"


def fresh_state() -> dict[str, Any]:
    model = resolve_model(os.getenv("FRIDAY_AI_MODEL", DEFAULT_MODEL))
    return {
        "name": "FRIDAY",
        "owner_name": OWNER_NAME,
        "owner_title": OWNER_TITLE,
        "wake_word": "hey friday",
        "model": model,
        "cloud_ready": openai_ready(),
        "memory_summary": "No stored memory yet.",
        "history": [],
        "events": [],
        "notes": [],
        "tasks": [],
        "facts": [],
        "command_memory": [],
        "contacts": [],
        "security_mode": "normal",
        "power_state": "online",
        "camera_status": {"camera": "idle", "face": "idle"},
        "modules": [
            {
                "name": "Voice",
                "status": "Armed",
                "detail": "Wake word and speech playback",
            },
            {
                "name": "Memory",
                "status": "Live",
                "detail": "History, notes, and tasks",
            },
            {
                "name": "Automation",
                "status": "Ready",
                "detail": "Planning, app control, and downloads",
            },
            {
                "name": "Analytics",
                "status": "Live",
                "detail": "CPU, GPU, RAM, network, and battery",
            },
            {
                "name": "Security",
                "status": "Ready",
                "detail": "Power state, lock, and voice control",
            },
            {
                "name": "Vision",
                "status": "Idle",
                "detail": "Camera and face status",
            },
        ],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def load_state() -> dict[str, Any]:
    state = fresh_state()
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = None
        if isinstance(raw, dict):
            for key in (
                "owner_name",
                "owner_title",
                "wake_word",
                "model",
                "cloud_ready",
                "memory_summary",
                "history",
                "events",
                "notes",
                "tasks",
                "facts",
                "command_memory",
                "contacts",
                "security_mode",
                "power_state",
                "camera_status",
                "modules",
                "created_at",
            ):
                if key in raw:
                    state[key] = raw[key]
    state["owner_name"] = OWNER_NAME
    state["owner_title"] = OWNER_TITLE
    state["model"] = resolve_model(str(state.get("model") or DEFAULT_MODEL))
    state["cloud_ready"] = openai_ready()
    return state


STATE = load_state()


def save_state() -> None:
    with STATE_LOCK:
        _write_state_file_locked()


def _write_state_file_locked() -> None:
    payload = json.dumps(STATE, indent=2, ensure_ascii=False)
    tmp_file = STATE_FILE.with_suffix(".tmp")
    tmp_file.write_text(payload, encoding="utf-8")
    tmp_file.replace(STATE_FILE)


def touch_state() -> None:
    STATE["updated_at"] = now_iso()


def trim_lists() -> None:
    STATE["history"] = (STATE.get("history") or [])[-MAX_HISTORY:]
    STATE["events"] = (STATE.get("events") or [])[-MAX_EVENTS:]
    STATE["notes"] = (STATE.get("notes") or [])[-MAX_NOTES:]
    STATE["tasks"] = (STATE.get("tasks") or [])[-MAX_TASKS:]
    STATE["facts"] = (STATE.get("facts") or [])[-MAX_FACTS:]
    STATE["command_memory"] = (STATE.get("command_memory") or [])[-MAX_COMMAND_MEMORY:]


def record_history(role: str, text: str) -> None:
    history = STATE.setdefault("history", [])
    history.append({"id": new_id("msg"), "role": role, "text": text, "ts": now_iso()})
    trim_lists()
    touch_state()


def record_event(kind: str, text: str, extra: dict[str, Any] | None = None) -> None:
    event = {"id": new_id("evt"), "kind": kind, "text": text, "ts": now_iso()}
    if extra:
        event["extra"] = extra
    STATE.setdefault("events", []).append(event)
    trim_lists()
    touch_state()


def record_command_memory(text: str, source: str) -> None:
    command_text = text.strip()
    if not command_text:
        return
    STATE.setdefault("command_memory", []).append(
        {"id": new_id("cmd"), "text": command_text, "source": source, "ts": now_iso()}
    )
    trim_lists()
    touch_state()


def build_memory_summary() -> str:
    notes = [item["text"] for item in STATE.get("notes", [])[-5:]]
    tasks = [item["text"] for item in STATE.get("tasks", []) if not item.get("done")][:5]
    facts = [f"{item.get('key')}: {item.get('value')}" for item in STATE.get("facts", [])[-5:]]
    replies = [item["text"] for item in STATE.get("history", []) if item.get("role") == "friday"][-3:]
    commands = [item["text"] for item in STATE.get("command_memory", [])[-3:]]
    parts: list[str] = []
    parts.append(f"Owner: {STATE.get('owner_name', OWNER_NAME)} ({STATE.get('owner_title', OWNER_TITLE)})")
    if facts:
        parts.append(f"Facts: {', '.join(facts)}")
    if notes:
        parts.append(f"Notes: {', '.join(notes)}")
    if tasks:
        parts.append(f"Open tasks: {', '.join(tasks)}")
    if commands:
        parts.append(f"Recent commands: {', '.join(commands)}")
    if replies:
        parts.append(f"Recent FRIDAY replies: {replies[-1]}")
    return " | ".join(parts) if parts else "No stored memory yet."


def rebuild_memory_summary() -> None:
    STATE["memory_summary"] = build_memory_summary()
    touch_state()


def public_state() -> dict[str, Any]:
    payload = deepcopy(STATE)
    payload["supported_models"] = list(SUPPORTED_MODELS)
    payload["cloud_ready"] = openai_ready()
    payload["state_url"] = LOCAL_URL
    payload["owner_profile"] = {
        "name": STATE.get("owner_name", OWNER_NAME),
        "title": STATE.get("owner_title", OWNER_TITLE),
    }
    return payload


def smart_capabilities() -> str:
    return (
        "I can chat, remember facts and notes, track tasks, plan multi-step commands, open apps, search the web, "
        "summarize local text files, set timers and reminders, capture screenshots, manage contacts, switch AI models, "
        "report telemetry, and keep owner context ready."
    )


def parse_json_body(raw_body: bytes) -> dict[str, Any]:
    if not raw_body:
        return {}
    data = json.loads(raw_body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def decode_audio_payload(audio_value: str) -> bytes:
    cleaned = str(audio_value or "").strip()
    if not cleaned:
        raise ValueError("Audio payload is required.")
    if "," in cleaned and cleaned.lower().startswith("data:"):
        cleaned = cleaned.split(",", 1)[1]
    return base64.b64decode(cleaned, validate=False)


def normalize_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"[,\.;:!?]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def strip_wake_word(text: str) -> str:
    lowered = normalize_text(text)
    for prefix in ("hey friday", "friday"):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :].strip(" ,.!?:;")
            break
    return lowered


def parse_duration_seconds(text: str) -> int | None:
    lowered = normalize_text(text)
    matches = re.findall(
        r"(\d+)\s*(seconds?|secs?|second|sec|minutes?|mins?|minute|min|hours?|hrs?|hour|hr)\b",
        lowered,
    )
    if matches:
        total = 0
        for value, unit in matches:
            number = int(value)
            if unit.startswith(("hour", "hr")):
                total += number * 3600
            elif unit.startswith(("minute", "min")):
                total += number * 60
            else:
                total += number
        return total or None
    if lowered.startswith("timer ") or lowered.startswith("remind "):
        plain = re.search(r"\b(\d+)\b", lowered)
        if plain:
            return int(plain.group(1)) * 60
    return None


def format_seconds(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{seconds} seconds"


MATH_NAMES = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
}


def _safe_math_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_math_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _safe_math_eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _safe_math_eval(node.left)
        right = _safe_math_eval(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 12:
                raise ValueError("Exponent too large.")
            return left**right
    if isinstance(node, ast.Name) and node.id in MATH_NAMES and isinstance(MATH_NAMES[node.id], (int, float)):
        return float(MATH_NAMES[node.id])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func = MATH_NAMES.get(node.func.id)
        if callable(func) and len(node.args) <= 2 and not node.keywords:
            return float(func(*[_safe_math_eval(arg) for arg in node.args]))
    raise ValueError("Unsupported expression.")


def calculate_expression(text: str) -> str | None:
    cleaned = normalize_text(text)
    if cleaned.startswith(("calculate ", "compute ", "what is ", "what's ")):
        expression = re.sub(r"^(?:calculate|compute|what\s+is|what's)\s+", "", text, flags=re.IGNORECASE)
    elif re.fullmatch(r"[\d\s+\-*/().%^]+", text.strip()):
        expression = text
    else:
        return None
    expression = expression.replace("^", "**")
    if not re.fullmatch(r"[\d\s+\-*/().%*,a-zA-Z_]+", expression):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_math_eval(tree)
    except Exception:
        return None
    rendered = str(int(result)) if result.is_integer() else f"{result:.8g}"
    return f"{expression.strip()} = {rendered}"


def resolve_path(raw_path: str) -> Path | None:
    candidate = Path(raw_path.strip().strip('"').strip("'")).expanduser()
    if candidate.exists():
        return candidate
    if not candidate.is_absolute():
        options = [BASE_DIR, Path.cwd(), BASE_DIR / "downloads", BASE_DIR / "captures"]
        for base in options:
            possible = (base / candidate).resolve()
            if possible.exists():
                return possible
    return None


def run_powershell_json(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "").strip() or "powershell_failed")
    payload = (completed.stdout or "").strip()
    if not payload:
        raise RuntimeError("empty_power_shell_output")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("invalid_metrics_payload")
    return data


def get_system_metrics(force: bool = False) -> dict[str, Any]:
    with METRICS_LOCK:
        cached_at = float(METRICS_CACHE.get("timestamp") or 0.0)
        if not force and METRICS_CACHE.get("data") and time.time() - cached_at < 2.5:
            return deepcopy(METRICS_CACHE["data"])

        fallback = {
            "cpu_percent": None,
            "ram": {"used_gb": None, "total_gb": None, "percent": None},
            "battery": {"percent": None, "status": None},
            "network": None,
            "gpu": {"name": None, "utilization": None, "memory_used": None, "memory_total": None},
            "processes": [],
            "uptime": None,
            "timestamp": now_iso(),
        }

        if os.name != "nt":
            METRICS_CACHE["timestamp"] = time.time()
            METRICS_CACHE["data"] = fallback
            return deepcopy(fallback)

        script = r"""
$ErrorActionPreference='SilentlyContinue'
$cpuValues = Get-CimInstance Win32_Processor | Select-Object -ExpandProperty LoadPercentage
$cpu = $null
if ($cpuValues) { $cpu = ($cpuValues | Measure-Object -Average).Average }
$osInfo = Get-CimInstance Win32_OperatingSystem
$totalGb = [math]::Round($osInfo.TotalVisibleMemorySize / 1MB, 2)
$freeGb = [math]::Round($osInfo.FreePhysicalMemory / 1MB, 2)
$usedGb = [math]::Round($totalGb - $freeGb, 2)
$uptime = $null
try {
    $boot = [System.Management.ManagementDateTimeConverter]::ToDateTime($osInfo.LastBootUpTime)
    $uptime = (New-TimeSpan -Start $boot -End (Get-Date)).ToString()
} catch {}
$battery = Get-CimInstance Win32_Battery | Select-Object -First 1
$batteryPercent = $null
$batteryStatus = $null
if ($battery) {
    $batteryPercent = $battery.EstimatedChargeRemaining
    $batteryStatus = $battery.BatteryStatus
}
$adapter = Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object -First 1
$network = $null
if ($adapter) {
    $stats = Get-NetAdapterStatistics -Name $adapter.Name
    $network = [ordered]@{
        name = $adapter.Name
        speed = $adapter.LinkSpeed
        received_mb = [math]::Round(($stats.ReceivedBytes / 1MB), 2)
        sent_mb = [math]::Round(($stats.SentBytes / 1MB), 2)
    }
}
$gpu = $null
try {
    $gpuLine = & nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null
    if ($LASTEXITCODE -eq 0 -and $gpuLine) {
        $line = ($gpuLine | Select-Object -First 1).ToString()
        $parts = $line -split ',\s*'
        if ($parts.Count -ge 4) {
            $gpu = [ordered]@{
                name = $parts[0].Trim()
                utilization = [double]$parts[1].Trim()
                memory_used = [double]$parts[2].Trim()
                memory_total = [double]$parts[3].Trim()
            }
        }
    }
} catch {}
if (-not $gpu) {
    $video = Get-CimInstance Win32_VideoController | Select-Object -First 1
    if ($video) {
        $gpu = [ordered]@{
            name = $video.Name
            utilization = $null
            memory_used = $null
            memory_total = $null
        }
    }
}
$processes = Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name,Id,CPU,@{Name='WorkingSetMB';Expression={[math]::Round($_.WorkingSet64 / 1MB, 2)}}
$result = [ordered]@{
    cpu_percent = if ($cpu -ne $null) { [math]::Round([double]$cpu, 1) } else { $null }
    ram = [ordered]@{
        used_gb = $usedGb
        total_gb = $totalGb
        percent = if ($totalGb -gt 0) { [math]::Round(($usedGb / $totalGb) * 100, 1) } else { $null }
    }
    battery = [ordered]@{
        percent = $batteryPercent
        status = $batteryStatus
    }
    network = $network
    gpu = $gpu
    processes = $processes
    uptime = $uptime
    timestamp = (Get-Date).ToString("o")
}
$result | ConvertTo-Json -Depth 5 -Compress
"""
        try:
            metrics = run_powershell_json(script)
        except Exception:
            metrics = fallback

        METRICS_CACHE["timestamp"] = time.time()
        METRICS_CACHE["data"] = metrics
        return deepcopy(metrics)


def format_metrics_summary(metrics: dict[str, Any]) -> str:
    cpu = metrics.get("cpu_percent")
    ram = metrics.get("ram") or {}
    gpu = metrics.get("gpu") or {}
    battery = metrics.get("battery") or {}
    network = metrics.get("network") or {}
    pieces: list[str] = []
    if cpu is not None:
        pieces.append(f"CPU {cpu}%")
    if ram.get("used_gb") is not None and ram.get("total_gb") is not None:
        pieces.append(f"RAM {ram['used_gb']} / {ram['total_gb']} GB")
    if gpu.get("name"):
        if gpu.get("utilization") is not None:
            pieces.append(f"GPU {gpu['name']} {gpu['utilization']}%")
        else:
            pieces.append(f"GPU {gpu['name']}")
    if battery.get("percent") is not None:
        pieces.append(f"Battery {battery['percent']}%")
    if network.get("name"):
        pieces.append(f"Network {network['name']}")
    return ", ".join(pieces) if pieces else "Telemetry is warming up."


def format_task_list() -> str:
    tasks = [item["text"] for item in STATE.get("tasks", []) if not item.get("done")]
    return ", ".join(tasks) if tasks else "No open tasks."


def format_note_list() -> str:
    notes = [item["text"] for item in STATE.get("notes", [])[-5:]]
    return ", ".join(notes) if notes else "No notes yet."


def format_fact_list() -> str:
    facts = [f"{item.get('key')}: {item.get('value')}" for item in STATE.get("facts", [])[-8:]]
    return ", ".join(facts) if facts else "No learned facts yet."


def build_context() -> str:
    metrics = get_system_metrics()
    return "\n".join(
        [
            f"System name: {STATE.get('name', 'FRIDAY')}",
            f"Owner: {STATE.get('owner_name', OWNER_NAME)} ({STATE.get('owner_title', OWNER_TITLE)})",
            f"Wake word: {STATE.get('wake_word', 'hey friday')}",
            f"Preferred model: {STATE.get('model', DEFAULT_MODEL)}",
            f"Memory summary: {STATE.get('memory_summary', 'No stored memory yet.')}",
            f"Learned facts: {format_fact_list()}",
            f"Notes: {format_note_list()}",
            f"Open tasks: {format_task_list()}",
            f"Capabilities: {smart_capabilities()}",
            f"Security mode: {STATE.get('security_mode', 'normal')}",
            f"Power state: {STATE.get('power_state', 'online')}",
            f"Telemetry: {format_metrics_summary(metrics)}",
        ]
    )


def set_model(model_name: str) -> tuple[bool, str]:
    candidate = resolve_model(model_name)
    if candidate not in SUPPORTED_MODELS:
        return False, "Unsupported model."
    STATE["model"] = candidate
    touch_state()
    rebuild_memory_summary()
    save_state()
    record_event("model", f"Preferred model set to {candidate}.")
    save_state()
    return True, candidate


def add_note(text: str) -> str:
    note = text.strip()
    if not note:
        return "Give me a note to store."
    STATE.setdefault("notes", []).append(
        {"id": new_id("note"), "text": note, "created_at": now_iso()}
    )
    trim_lists()
    rebuild_memory_summary()
    record_event("note", f"Saved note: {note}")
    save_state()
    return f"Saved note: {note}"


def remember_fact(key: str, value: str) -> str:
    clean_key = normalize_text(key).strip()
    clean_value = value.strip()
    if not clean_key or not clean_value:
        return "Tell me what fact to remember."

    facts = STATE.setdefault("facts", [])
    for item in facts:
        if normalize_text(str(item.get("key", ""))) == clean_key:
            item["key"] = key.strip()
            item["value"] = clean_value
            item["updated_at"] = now_iso()
            rebuild_memory_summary()
            record_event("memory", f"Updated fact: {item['key']}.")
            save_state()
            return f"Remembered: {item['key']} is {clean_value}."

    facts.append({"id": new_id("fact"), "key": key.strip(), "value": clean_value, "created_at": now_iso()})
    trim_lists()
    rebuild_memory_summary()
    record_event("memory", f"Learned fact: {key.strip()}.")
    save_state()
    return f"Remembered: {key.strip()} is {clean_value}."


def extract_fact_from_text(text: str) -> tuple[str, str] | None:
    cleaned = text.strip().strip(".")
    patterns = (
        r"^(?:remember|note)\s+(?:that\s+)?(?P<key>.+?)\s+(?:is|are|=)\s+(?P<value>.+)$",
        r"^(?:my|the)\s+(?P<key>.+?)\s+(?:is|are|=)\s+(?P<value>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            key = match.group("key").strip()
            value = match.group("value").strip()
            if key and value and len(key) <= 80 and len(value) <= 220:
                return key, value
    return None


def recall_memory(query: str = "") -> str:
    lowered = normalize_text(query)
    facts = STATE.get("facts", [])
    if lowered:
        for item in facts:
            key = normalize_text(str(item.get("key", "")))
            value = str(item.get("value") or "").strip()
            if key and value and (key in lowered or lowered in key):
                return f"{item.get('key')} is {value}."
    summary = STATE.get("memory_summary") or build_memory_summary()
    return summary if summary and summary != "No stored memory yet." else "No stored memory yet."


def add_task(text: str) -> str:
    task = text.strip()
    if not task:
        return "Give me a task to track."
    STATE.setdefault("tasks", []).append(
        {"id": new_id("task"), "text": task, "done": False, "created_at": now_iso()}
    )
    trim_lists()
    rebuild_memory_summary()
    record_event("task", f"Tracked task: {task}")
    save_state()
    return f"Task added: {task}"


def complete_task(target: str) -> str:
    lowered = normalize_text(target)
    tasks = STATE.get("tasks", [])
    best_item: dict[str, Any] | None = None
    best_score = 0.0
    for item in tasks:
        task_text = normalize_text(item.get("text", ""))
        if lowered == item.get("id") or lowered == task_text:
            item["done"] = True
            rebuild_memory_summary()
            record_event("task", f"Completed task: {item['text']}")
            save_state()
            return f"Marked complete: {item['text']}"
        if lowered and task_text:
            score = SequenceMatcher(None, lowered, task_text).ratio()
            if lowered in task_text or task_text in lowered:
                score = max(score, 0.88)
            if score > best_score:
                best_score = score
                best_item = item
    if best_item and best_score >= 0.72:
        best_item["done"] = True
        rebuild_memory_summary()
        record_event("task", f"Completed task: {best_item['text']}")
        save_state()
        return f"Marked complete: {best_item['text']}"
    return "I could not find that task."


def open_target(target: str) -> str:
    cleaned = target.strip().strip('"').strip("'")
    if not cleaned:
        return "I need a target to open."
    lookup = APP_ALIASES.get(cleaned.lower(), cleaned)
    if lookup.startswith(("http://", "https://", "steam://")):
        try:
            os.startfile(lookup)
        except Exception:
            webbrowser.open(lookup)
        return f"Opening {cleaned}."
    candidate = Path(lookup).expanduser()
    if candidate.exists():
        try:
            os.startfile(str(candidate))
            return f"Opening {candidate.name}."
        except Exception:
            pass
    try:
        os.startfile(lookup)
        return f"Launching {cleaned}."
    except Exception:
        subprocess.Popen(f'start "" "{lookup}"', shell=True)
        return f"Launching {cleaned}."


def close_target(target: str) -> str:
    cleaned = target.strip().strip('"').strip("'")
    if not cleaned:
        return "I need a target to close."
    base_name = Path(cleaned).name
    if base_name.lower().endswith(".exe"):
        candidates = [base_name]
    else:
        candidates = [base_name, f"{base_name}.exe"]
    for candidate in candidates:
        subprocess.run(["taskkill", "/IM", candidate, "/F"], capture_output=True, text=True)
    return f"Closing {cleaned}."


def lock_pc() -> str:
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
    return "Locking the screen."


def search_web(query: str) -> str:
    term = query.strip()
    if not term:
        return "Tell me what to search for."
    url = "https://www.google.com/search?q=" + quote_plus(term)
    webbrowser.open(url)
    return f"Searching the web for {term}."


def capture_screenshot() -> str:
    captures_dir = BASE_DIR / "captures"
    captures_dir.mkdir(exist_ok=True)
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = captures_dir / filename
    script = f"""
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save('{str(path).replace("'", "''")}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Output '{path.name}'
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            record_event("screenshot", f"Captured {path.name}.")
            save_state()
            return f"Screenshot saved to captures/{path.name}."
        error = (result.stderr or result.stdout or "").strip() or "Screenshot failed."
    except Exception as exc:
        error = str(exc)
    return error


def download_direct_file(url: str) -> str:
    cleaned = url.strip().strip('"').strip("'")
    url_match = re.search(r"https?://[^\s\"']+", cleaned)
    if url_match:
        cleaned = url_match.group(0)
    if not cleaned.startswith(("http://", "https://")):
        return "Give me a direct https link."
    downloads_dir = BASE_DIR / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    parsed = urlparse(cleaned)
    filename = Path(parsed.path).name or f"download_{int(time.time())}"
    if "." not in filename:
        filename += ".mp4" if "mp4" in cleaned.lower() else ".bin"
    target = downloads_dir / filename
    try:
        response = requests.get(cleaned, stream=True, timeout=45)
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)
        record_event("download", f"Saved {target.name}.", {"source": cleaned})
        save_state()
        return f"Downloaded {target.name} to downloads."
    except Exception as exc:
        return f"Download failed: {exc}"


def set_security_mode(mode: str) -> str:
    normalized = normalize_text(mode)
    if normalized in {"normal", "standard", "ready"}:
        normalized = "normal"
    elif normalized in {"shield", "secure", "security"}:
        normalized = "shield"
    elif normalized in {"silent", "quiet"}:
        normalized = "silent"
    elif normalized in {"lockdown", "lock"}:
        normalized = "lockdown"
    else:
        return "Use normal, shield, silent, or lockdown."

    STATE["security_mode"] = normalized
    if normalized == "lockdown":
        STATE["power_state"] = "standby"
        try:
            lock_pc()
        except Exception:
            pass
    touch_state()
    record_event("security", f"Security mode set to {normalized}.")
    save_state()
    if normalized == "lockdown":
        return "Security lockdown engaged. Screen locked."
    if normalized == "shield":
        return "Security shield engaged."
    if normalized == "silent":
        return "Silent security mode engaged."
    return "Security mode set to normal."


def set_power_state(mode: str) -> str:
    normalized = normalize_text(mode)
    if normalized in {"power up", "up", "online", "resume", "wake"}:
        normalized = "online"
    elif normalized in {"power down", "down", "standby", "sleep"}:
        normalized = "standby"
    else:
        return "Use power up or power down."

    STATE["power_state"] = normalized
    touch_state()
    record_event("power", f"Power state set to {normalized}.")
    save_state()
    if normalized == "online":
        return "FRIDAY is online."
    return "FRIDAY is in standby."


def control_pc_power(action: str) -> str:
    normalized = normalize_text(action)
    if normalized in {"lock", "secure"}:
        return lock_pc()
    if normalized in {"sleep", "hibernate", "shutdown", "restart", "logoff"}:
        commands = {
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "hibernate": "shutdown /h",
            "shutdown": "shutdown /s /t 0",
            "restart": "shutdown /r /t 0",
            "logoff": "shutdown /l",
        }
        command = commands.get(normalized)
        if not command:
            return "Unsupported power action."
        try:
            subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
            record_event("power", f"PC power action: {normalized}.")
            save_state()
            return f"PC {normalized} command sent."
        except Exception as exc:
            return f"Power action failed: {exc}"
    return "Use sleep, hibernate, shutdown, restart, logoff, or lock."


def camera_face_status() -> str:
    camera = STATE.get("camera_status") or {}
    camera_state = str(camera.get("camera") or "idle")
    face_state = str(camera.get("face") or "idle")
    return f"Camera {camera_state}. Face status {face_state}."


def update_camera_face_status(camera_state: str | None = None, face_state: str | None = None) -> None:
    current = STATE.setdefault("camera_status", {"camera": "idle", "face": "idle"})
    if camera_state is not None:
        current["camera"] = camera_state
    if face_state is not None:
        current["face"] = face_state
    touch_state()
    save_state()


def find_contact(target: str) -> dict[str, Any] | None:
    lookup = normalize_text(target)
    if not lookup:
        return None
    for item in STATE.get("contacts", []):
        if lookup == normalize_text(str(item.get("name", ""))):
            return item
    return None


def add_contact(name: str, phone: str | None = None, email: str | None = None) -> str:
    clean_name = name.strip()
    if not clean_name:
        return "Give me a contact name."
    contacts = STATE.setdefault("contacts", [])
    existing = find_contact(clean_name)
    payload = {
        "id": new_id("contact"),
        "name": clean_name,
        "phone": (phone or "").strip() or None,
        "email": (email or "").strip() or None,
        "created_at": now_iso(),
    }
    if existing:
        existing.update({key: value for key, value in payload.items() if value is not None})
        reply = f"Updated contact {clean_name}."
    else:
        contacts.append(payload)
        reply = f"Saved contact {clean_name}."
    trim_lists()
    touch_state()
    record_event("contact", reply)
    save_state()
    return reply


def call_contact(target: str) -> str:
    contact = find_contact(target)
    if contact:
        phone = str(contact.get("phone") or "").strip()
        if phone:
            try:
                os.startfile(f"tel:{phone}")
            except Exception:
                webbrowser.open(f"tel:{phone}")
            return f"Calling {contact.get('name', target)}."
        return f"{contact.get('name', target)} does not have a phone number saved."
    clean = target.strip()
    phone_match = re.search(r"(\+?\d[\d\s().-]{4,}\d)", clean)
    if phone_match:
        phone = phone_match.group(1).strip()
        try:
            os.startfile(f"tel:{phone}")
        except Exception:
            webbrowser.open(f"tel:{phone}")
        return f"Calling {phone}."
    return "Save the contact name and number first, or give me a phone number."


def message_contact(target: str) -> str:
    contact = find_contact(target)
    if contact:
        email = str(contact.get("email") or "").strip()
        phone = str(contact.get("phone") or "").strip()
        if email:
            try:
                os.startfile(f"mailto:{email}")
            except Exception:
                webbrowser.open(f"mailto:{email}")
            return f"Messaging {contact.get('name', target)} by email."
        if phone:
            try:
                os.startfile(f"sms:{phone}")
            except Exception:
                webbrowser.open(f"sms:{phone}")
            return f"Messaging {contact.get('name', target)}."
        return f"{contact.get('name', target)} does not have a message route saved."
    clean = target.strip()
    if "@" in clean:
        try:
            os.startfile(f"mailto:{clean}")
        except Exception:
            webbrowser.open(f"mailto:{clean}")
        return f"Opening a mail message to {clean}."
    phone_match = re.search(r"(\+?\d[\d\s().-]{4,}\d)", clean)
    if phone_match:
        phone = phone_match.group(1).strip()
        try:
            os.startfile(f"sms:{phone}")
        except Exception:
            webbrowser.open(f"sms:{phone}")
        return f"Opening a message to {phone}."
    return "Save the contact name first, or give me an email address or phone number."


def read_text_file(path_text: str) -> tuple[str | None, str | None]:
    candidate = resolve_path(path_text)
    if candidate is None or not candidate.exists():
        return None, "I could not find that file."
    if candidate.is_dir():
        return None, "That path is a folder, not a file."
    if candidate.suffix.lower() not in {
        ".txt",
        ".md",
        ".json",
        ".py",
        ".csv",
        ".log",
        ".html",
        ".css",
        ".js",
        ".yml",
        ".yaml",
    }:
        return None, f"I can read text files right now. {candidate.suffix or 'That file'} is not supported yet."
    try:
        content = candidate.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)
    return content[:12000], None


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw_xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(raw_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall("x:si", namespace):
        pieces = [node.text or "" for node in item.findall(".//x:t", namespace)]
        strings.append("".join(pieces).strip())
    return strings


def _xlsx_cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cell_type = cell.attrib.get("t")
    value_node = cell.find("x:v", namespace)
    if cell_type == "inlineStr":
        pieces = [node.text or "" for node in cell.findall(".//x:t", namespace)]
        return " ".join("".join(pieces).split())
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text.strip()
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except Exception:
            return ""
    return raw_value


def find_journal_names_file() -> Path | None:
    if JOURNAL_NAMES_FILE.exists():
        return JOURNAL_NAMES_FILE

    search_roots = [
        JOURNAL_NAMES_DIR,
        Path.home() / "Downloads",
        Path.home() / "OneDrive" / "Downloads",
        BASE_DIR,
    ]
    best_match: Path | None = None
    for root in search_roots:
        if not root.exists():
            continue
        try:
            files = root.rglob("*.xlsx") if root != BASE_DIR else root.glob("*.xlsx")
            for candidate in files:
                normalized_name = normalize_text(candidate.stem.replace("ı", "i").replace("İ", "i"))
                if "jurnal" in normalized_name and (
                    "sirasi" in normalized_name
                    or "siras" in normalized_name
                    or "sira" in normalized_name
                ):
                    return candidate
                if best_match is None and "jurnal" in normalized_name:
                    best_match = candidate
        except Exception:
            continue
    return best_match


def load_journal_kid_names(path: Path | None = None) -> tuple[list[str], str | None]:
    path = path or find_journal_names_file()
    if path is None:
        return [], (
            "Boss, jurnal faylını tapa bilmədim. Faylı Downloads qovluğunda saxla, "
            "ya da FRIDAY_JOURNAL_NAMES_FILE ilə dəqiq yolu göstər."
        )
    if not path.exists():
        return [], f"Jurnal faylını tapa bilmədim: {path}"
    try:
        with zipfile.ZipFile(path) as archive:
            workbook_xml = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            rels_xml = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            workbook_ns = {
                "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
                "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            }
            rels_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
            first_sheet = workbook_xml.find("x:sheets/x:sheet", workbook_ns)
            if first_sheet is None:
                return [], "Jurnalda vərəq tapmadım."
            rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = None
            for rel in rels_xml.findall("r:Relationship", rels_ns):
                if rel.attrib.get("Id") == rel_id:
                    target = rel.attrib.get("Target")
                    break
            sheet_path = "xl/" + (target or "worksheets/sheet1.xml").lstrip("/")
            shared_strings = _xlsx_shared_strings(archive)
            sheet_xml = ElementTree.fromstring(archive.read(sheet_path))
    except Exception as exc:
        return [], f"Jurnalı oxuya bilmədim: {exc}"

    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    names: list[str] = []
    seen: set[str] = set()
    for row in sheet_xml.findall(".//x:sheetData/x:row", namespace):
        first_cell = None
        for cell in row.findall("x:c", namespace):
            ref = cell.attrib.get("r", "")
            if ref.startswith("A"):
                first_cell = cell
                break
        if first_cell is None:
            continue
        name = _xlsx_cell_text(first_cell, shared_strings)
        name = " ".join(name.replace("`", "").split())
        normalized = normalize_text(name)
        if name and normalized not in seen:
            seen.add(normalized)
            names.append(name)
    return names, None


def format_kid_names_azerbaijani(names: list[str]) -> str:
    if not names:
        return "Boss, jurnalda uşaq adı tapmadım."
    ordinal_words = [
        "Birinci",
        "İkinci",
        "Üçüncü",
        "Dördüncü",
        "Beşinci",
        "Altıncı",
        "Yeddinci",
        "Səkkizinci",
        "Doqquzuncu",
        "Onuncu",
    ]
    entries: list[str] = []
    for index, name in enumerate(names, start=1):
        label = ordinal_words[index - 1] if index <= len(ordinal_words) else f"{index}-ci"
        entries.append(f"{label}: {name}")
    return f"Əlbəttə, Boss. Jurnaldakı uşaqların adları belədir:\n" + "\n".join(entries)


def tell_kid_names() -> str:
    names, error = load_journal_kid_names()
    if error:
        return error
    record_event("journal", f"Read {len(names)} names from journal.")
    save_state()
    return format_kid_names_azerbaijani(names)


def is_kid_names_request(text: str) -> bool:
    lowered = normalize_text(text.replace("'", " ").replace("ı", "i").replace("İ", "i"))
    phrases = (
        "tell me kids names",
        "tell me kid names",
        "tell me the kids name",
        "tell me the kids names",
        "kids names",
        "kid names",
        "student names",
        "students names",
        "children names",
        "jurnal sirasi",
        "jurnal sirası",
        "jurnal sira",
        "usaqlarin adlari",
        "usaqlarin adlarini de",
        "uşaqlarin adlari",
        "uşaqlarin adlarini de",
        "sagirdlerin adlari",
        "sagirdlerin adlarini de",
        "şagirdlərin adlari",
        "şagirdlərin adlarini de",
    )
    if any(phrase in lowered for phrase in phrases):
        return True
    has_name_word = any(word in lowered for word in ("name", "names", "ad", "adlari", "adlarini"))
    has_student_word = any(word in lowered for word in ("kid", "kids", "student", "students", "child", "children", "usaq", "uşaq", "sagird", "şagird"))
    return has_name_word and has_student_word


def summarize_document(path_text: str) -> str:
    content, error = read_text_file(path_text)
    if error:
        return error
    if content is None:
        return "I could not read that file."

    path = resolve_path(path_text)
    assert path is not None
    prompt = "\n".join(
        [
            "Summarize this document clearly and concisely.",
            "Return a clean summary with the main points first.",
            f"File: {path.name}",
            "",
            content,
        ]
    )
    reply, reply_error = generate_reply(
        prompt,
        history=STATE.get("history", []),
        context=build_context(),
        model=STATE.get("model", DEFAULT_MODEL),
        temperature=0.2,
        max_completion_tokens=420,
    )
    if reply:
        record_event("document", f"Summarized {path.name}.")
        save_state()
        return reply
    preview = content.strip().splitlines()[:10]
    summary = " ".join(preview)[:900].strip()
    record_event("document", f"Previewed {path.name}.")
    save_state()
    return summary or reply_error or "I could not summarize that file."


def schedule_timer(seconds: int, label: str, reminder: bool = False) -> str:
    title = label.strip() or "Timer"

    def trigger() -> None:
        with STATE_LOCK:
            message = f"{title} finished."
            if reminder:
                message = f"Reminder: {title}"
            record_event("timer", message, {"seconds": seconds})
            _write_state_file_locked()

    timer = threading.Timer(seconds, trigger)
    timer.daemon = True
    timer.start()
    kind = "reminder" if reminder else "timer"
    record_event(kind, f"{title} scheduled for {seconds} seconds.", {"seconds": seconds})
    save_state()
    return f"{title} set for {format_seconds(seconds)}."


def parse_model_choice(text: str) -> str | None:
    lowered = normalize_text(text)
    for model in MODEL_LOOKUP:
        if model in lowered:
            return model
    return None


def should_plan_command(text: str) -> bool:
    lowered = normalize_text(strip_wake_word(text))
    if not lowered:
        return False
    if any(marker in lowered for marker in (" and then ", " then ", " after that ", " followed by ", ";")):
        return True
    verbs = (
        "open",
        "launch",
        "start",
        "search",
        "note",
        "task",
        "timer",
        "remind",
        "call",
        "message",
        "text",
        "screenshot",
        "download",
        "lock",
        "power",
        "sleep",
        "shutdown",
        "restart",
        "read",
        "summarize",
        "camera",
        "face",
    )
    hits = sum(1 for verb in verbs if re.search(rf"\b{re.escape(verb)}\b", lowered))
    return hits >= 2 and len(lowered.split()) >= 6


def build_command_plan(text: str, source: str = "typed") -> list[str]:
    cleaned = strip_wake_word(text)
    lowered = normalize_text(cleaned)
    if not should_plan_command(cleaned):
        return [cleaned]

    if openai_ready():
        prompt = "\n".join(
            [
                "You are FRIDAY's command planner.",
                "Break the user request into ordered local actions.",
                "Return only JSON with this shape:",
                '{"steps":["step 1","step 2"],"summary":"short summary"}',
                "Each step must be a concise command FRIDAY can execute locally.",
                "Do not include commentary or markdown.",
                "",
                f"User text: {cleaned}",
            ]
        )
        payload, error = request_json(prompt, model=STATE.get("model", DEFAULT_MODEL))
        if payload and not error:
            raw_steps = payload.get("steps")
            if isinstance(raw_steps, list):
                steps = [str(item).strip() for item in raw_steps if str(item).strip()]
                if len(steps) >= 2:
                    return steps

    parts = re.split(
        r"\b(?:and then|then|after that|followed by|next)\b|;",
        lowered or cleaned,
        flags=re.IGNORECASE,
    )
    steps = [part.strip(" ,.") for part in parts if part.strip(" ,.")]
    if len(steps) < 2 and " and " in lowered:
        and_parts = re.split(r"\s+and\s+", lowered or cleaned, flags=re.IGNORECASE)
        and_steps = [part.strip(" ,.") for part in and_parts if part.strip(" ,.")]
        if len(and_steps) >= 2:
            steps = and_steps
    if len(steps) >= 2:
        return steps
    return [cleaned]


def execute_command_plan(steps: list[str], source: str = "typed") -> dict[str, Any]:
    replies: list[str] = []
    handled_any = False
    for index, step in enumerate(steps, start=1):
        routed = route_command(step, source=source, allow_planning=False)
        handled_any = handled_any or routed.get("handled", False)
        reply = str(routed.get("reply") or "").strip()
        if reply:
            replies.append(f"Step {index}: {reply}")
    if not replies:
        return {"handled": False, "reply": "", "kind": "conversation"}
    record_event("plan", f"Executed {len(steps)} planned steps.")
    return {"handled": handled_any, "reply": " | ".join(replies), "kind": "plan"}


def route_voice_command(raw_text: str) -> dict[str, Any] | None:
    text = strip_wake_word(raw_text)
    lowered = normalize_text(text)
    if not lowered:
        return None

    lowered = re.sub(
        r"^(?:could you|can you|would you|will you|please|please could you|please can you|please would you)\s+",
        "",
        lowered,
    ).strip()

    open_match = re.search(
        r"\b(?:open|launch|start|run|bring up|show)\b\s+(?P<target>.+)$",
        lowered,
    )
    if open_match:
        target = open_match.group("target").strip()
        target = re.sub(r"\bfor me\b$", "", target).strip()
        target = re.sub(r"^(?:the|my)\s+", "", target).strip()
        if not target:
            return {"handled": True, "reply": "I need a target to open.", "kind": "open"}
        return {"handled": True, "reply": open_target(target), "kind": "open"}

    close_match = re.search(
        r"\b(?:close|quit|stop|exit)\b\s+(?P<target>.+)$",
        lowered,
    )
    if close_match:
        target = close_match.group("target").strip()
        target = re.sub(r"\bfor me\b$", "", target).strip()
        target = re.sub(r"^(?:the|my)\s+", "", target).strip()
        if not target:
            return {"handled": True, "reply": "I need a target to close.", "kind": "close"}
        return {"handled": True, "reply": close_target(target), "kind": "close"}

    search_match = re.search(
        r"\b(?:search|look up|find)\b(?:\s+(?:the\s+)?(?:internet|web|online))?(?:\s+for)?\s+(?P<query>.+)$",
        lowered,
    )
    if search_match:
        query = search_match.group("query").strip()
        query = re.sub(r"\bfor me\b$", "", query).strip()
        query = re.sub(r"^(?:the|my)\s+", "", query).strip()
        if query:
            return {"handled": True, "reply": search_web(query), "kind": "search"}

    if lowered.startswith(("call ", "message ", "text ")):
        target = text.split(" ", 1)[1] if " " in text else ""
        if lowered.startswith("call "):
            return {"handled": True, "reply": call_contact(target), "kind": "contact"}
        return {"handled": True, "reply": message_contact(target), "kind": "contact"}

    timer_match = re.search(
        r"\b(?:(?:set|start)\s+)?(?:a\s+)?(?P<kind>timer|reminder)\b(?:\s+for)?\s+(?P<label>.+)$",
        lowered,
    )
    if timer_match:
        label_text = timer_match.group("label").strip()
        seconds = parse_duration_seconds(label_text)
        if seconds is None:
            seconds = parse_duration_seconds(lowered)
        if seconds and seconds > 0:
            reminder_mode = timer_match.group("kind") == "reminder"
            clean_label = re.sub(r"\b(?:in|for)\s+\d+\s*(seconds?|secs?|second|sec|minutes?|mins?|minute|min|hours?|hrs?|hour|hr)\b.*$", "", label_text).strip()
            return {
                "handled": True,
                "reply": schedule_timer(seconds, clean_label or "Reminder", reminder=reminder_mode),
                "kind": "timer",
            }

    return None


def route_command(raw_text: str, source: str = "typed", allow_planning: bool = True) -> dict[str, Any]:
    original = (raw_text or "").strip()
    text = strip_wake_word(original)
    lowered = normalize_text(text)
    if allow_planning and should_plan_command(original):
        planned_steps = build_command_plan(original, source=source)
        if len(planned_steps) > 1:
            return execute_command_plan(planned_steps, source=source)
    if normalize_text(source) == "voice":
        voice_routed = route_voice_command(original)
        if voice_routed is not None:
            return voice_routed
    if not lowered:
        return {"handled": True, "reply": "Online.", "kind": "greeting"}

    if lowered in {"hi", "hello", "hey", "good morning", "good evening", "good night"}:
        return {"handled": True, "reply": "Online and ready.", "kind": "greeting"}

    if lowered in {"help", "commands", "capabilities"} or any(
        phrase in lowered for phrase in ("what can you do", "show commands", "list commands")
    ):
        return {"handled": True, "reply": smart_capabilities(), "kind": "help"}

    if is_kid_names_request(text):
        return {"handled": True, "reply": tell_kid_names(), "kind": "journal"}

    if lowered in {"who am i", "what is my name", "who's the boss", "who is the boss", "boss mode"}:
        owner_name = STATE.get("owner_name", OWNER_NAME)
        return {"handled": True, "reply": f"You are {owner_name}, {OWNER_TITLE}.", "kind": "owner"}

    if lowered.startswith(("what do you remember", "recall ", "memory summary", "what is my ", "what's my ")):
        query = text
        for prefix in ("what do you remember about ", "what do you remember", "recall ", "memory summary", "what is my ", "what's my "):
            if lowered.startswith(prefix):
                query = text[len(prefix) :]
                break
        return {"handled": True, "reply": recall_memory(query), "kind": "memory"}

    math_reply = calculate_expression(text)
    if math_reply:
        return {"handled": True, "reply": math_reply, "kind": "math"}

    fact = extract_fact_from_text(text)
    if fact:
        key, value = fact
        return {"handled": True, "reply": remember_fact(key, value), "kind": "memory"}

    if lowered.startswith(("set model to ", "switch model to ", "use model ", "model ")):
        candidate = parse_model_choice(lowered)
        if candidate:
            ok, result = set_model(candidate)
            if ok:
                return {
                    "handled": True,
                    "reply": f"Preferred model set to {result}.",
                    "kind": "model",
                }
        return {"handled": True, "reply": "I only support gpt-5, gpt-5-mini, gpt-4.1, and gpt-4o.", "kind": "model"}

    if lowered.startswith(("add note ", "note ", "remember ")):
        note_text = text.split(" ", 1)[1] if " " in text else ""
        if lowered.startswith("add note "):
            note_text = text[9:]
        elif lowered.startswith("remember "):
            note_text = text[9:]
        return {"handled": True, "reply": add_note(note_text), "kind": "note"}

    if lowered.startswith(("add task ", "task ", "todo ")):
        task_text = text.split(" ", 1)[1] if " " in text else ""
        if lowered.startswith("add task "):
            task_text = text[9:]
        elif lowered.startswith("todo "):
            task_text = text[5:]
        return {"handled": True, "reply": add_task(task_text), "kind": "task"}

    if lowered.startswith(("timer ", "set timer ", "start timer ", "remind me ", "reminder ", "set reminder ")):
        seconds = parse_duration_seconds(text)
        if seconds is None or seconds <= 0:
            return {
                "handled": True,
                "reply": "Give me a duration like 5 minutes or 30 seconds.",
                "kind": "timer",
            }
        label = text
        for prefix in ("set timer ", "start timer ", "timer ", "set reminder ", "reminder ", "remind me "):
            if lowered.startswith(prefix):
                label = text[len(prefix) :]
                break
        for marker in (" to ", " for ", " about "):
            marker_index = label.lower().find(marker)
            if marker_index >= 0:
                label = label[marker_index + len(marker) :]
                break
        reminder_mode = lowered.startswith(("remind me ", "reminder ", "set reminder "))
        return {
            "handled": True,
            "reply": schedule_timer(seconds, label.strip() or "Reminder", reminder=reminder_mode),
            "kind": "timer",
        }

    if lowered.startswith(("complete task ", "finish task ", "done ")):
        target = text.split(" ", 1)[1] if " " in text else ""
        if lowered.startswith("done "):
            target = text[5:]
        elif lowered.startswith("complete task "):
            target = text[14:]
        elif lowered.startswith("finish task "):
            target = text[12:]
        return {"handled": True, "reply": complete_task(target), "kind": "task"}

    if "clear memory" in lowered or "reset memory" in lowered:
        STATE["history"] = []
        STATE["events"] = []
        STATE["notes"] = []
        STATE["tasks"] = []
        STATE["facts"] = []
        STATE["command_memory"] = []
        STATE["memory_summary"] = "No stored memory yet."
        touch_state()
        save_state()
        return {"handled": True, "reply": "Memory cleared.", "kind": "memory"}

    if lowered.startswith(("open ", "launch ", "start ")):
        target = text.split(" ", 1)[1] if " " in text else ""
        return {"handled": True, "reply": open_target(target), "kind": "open"}

    if lowered.startswith(("close ", "quit ", "stop ")):
        target = text.split(" ", 1)[1] if " " in text else ""
        return {"handled": True, "reply": close_target(target), "kind": "close"}

    if lowered.startswith(("search ", "look up ", "find ", "search web for ")):
        query = text
        for prefix in ("search web for ", "look up ", "search ", "find "):
            if lowered.startswith(prefix):
                query = text[len(prefix) :]
                break
        return {"handled": True, "reply": search_web(query), "kind": "search"}

    if lowered.startswith(("call ", "message ", "text ")):
        target = text.split(" ", 1)[1] if " " in text else ""
        if lowered.startswith("call "):
            return {"handled": True, "reply": call_contact(target), "kind": "contact"}
        return {"handled": True, "reply": message_contact(target), "kind": "contact"}

    if lowered.startswith(("download mp4 ", "download direct link ", "download file ", "save mp4 ")):
        source_text = text.split(" ", 2)[-1] if " " in text else ""
        url_match = re.search(r"https?://\S+", text)
        url = url_match.group(0) if url_match else source_text
        return {"handled": True, "reply": download_direct_file(url), "kind": "download"}

    if re.search(r"\b(?:screenshot|capture\s+(?:the\s+)?screen|take\s+(?:a\s+)?screenshot|grab\s+screen)\b", lowered):
        return {"handled": True, "reply": capture_screenshot(), "kind": "screenshot"}

    if lowered.startswith(("camera status", "face status", "vision status")):
        return {"handled": True, "reply": camera_face_status(), "kind": "vision"}

    if lowered.startswith(("set security mode ", "security mode ", "lockdown mode ", "shield mode ", "silent mode ")):
        mode = re.sub(
            r"^(?:set\s+)?(?:security\s+mode|lockdown\s+mode|shield\s+mode|silent\s+mode)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        return {"handled": True, "reply": set_security_mode(mode), "kind": "security"}

    if lowered in {"power down", "power up", "standby", "resume"}:
        return {"handled": True, "reply": set_power_state(lowered), "kind": "power"}

    if lowered.startswith(("sleep pc", "hibernate pc", "shutdown pc", "restart pc", "logoff pc")):
        action = lowered.split(" ", 1)[0]
        return {"handled": True, "reply": control_pc_power(action), "kind": "power"}

    if lowered.startswith(("add contact ", "save contact ", "remember contact ")):
        payload = text.split(" ", 2)[2] if len(text.split(" ", 2)) >= 3 else ""
        name = payload
        phone = None
        email = None
        if ";" in payload:
            first, *rest = payload.split(";")
            name = first.strip()
            for chunk in rest:
                piece = chunk.strip()
                if piece.startswith("phone="):
                    phone = piece.split("=", 1)[1].strip()
                elif piece.startswith("email="):
                    email = piece.split("=", 1)[1].strip()
        return {"handled": True, "reply": add_contact(name, phone=phone, email=email), "kind": "contact"}

    if lowered.startswith(("read file ", "summarize file ", "summarize document ", "summarize ")):
        path_text = text
        for prefix in ("read file ", "summarize file ", "summarize document ", "summarize "):
            if lowered.startswith(prefix):
                path_text = text[len(prefix) :]
                break
        return {
            "handled": True,
            "reply": summarize_document(path_text),
            "kind": "document",
        }

    if "lock pc" in lowered or lowered == "lock":
        return {"handled": True, "reply": lock_pc(), "kind": "lock"}

    if lowered.startswith(("what time", "time now", "current time", "date now", "current date")):
        timestamp = datetime.now().strftime("%A, %B %d, %Y %H:%M")
        return {"handled": True, "reply": timestamp, "kind": "time"}

    if lowered.startswith(("status", "system status", "telemetry", "metrics")):
        metrics = get_system_metrics(force=True)
        summary = format_metrics_summary(metrics)
        return {"handled": True, "reply": summary, "kind": "metrics"}

    if lowered.startswith(("wake word ", "set wake word ", "change wake word ")):
        value = text.split(" ", 2)[-1].strip()
        if value:
            STATE["wake_word"] = value.lower()
            touch_state()
            rebuild_memory_summary()
            save_state()
            return {
                "handled": True,
                "reply": f"Wake word set to {STATE['wake_word']}.",
                "kind": "wake_word",
            }

    return {"handled": False, "reply": "", "kind": "conversation"}


VOICE_INTENT_KINDS = {
    "open",
    "close",
    "search",
    "note",
    "task",
    "timer",
    "reminder",
    "model",
    "time",
    "metrics",
    "lock",
    "wake_word",
    "clear_memory",
    "security",
    "power",
    "download",
    "screenshot",
    "contact",
    "vision",
    "owner",
    "conversation",
}


def classify_voice_intent(raw_text: str) -> dict[str, Any] | None:
    text = (raw_text or "").strip()
    if not text or not openai_ready():
        return None

    prompt = "\n".join(
        [
            "You are FRIDAY's voice intent parser.",
            "Decide whether the user's spoken text is a local operating-system command or normal conversation.",
            "Return only JSON with these keys:",
            "kind: one of open, close, search, note, task, timer, reminder, model, time, metrics, lock, wake_word, clear_memory, security, power, download, screenshot, contact, vision, owner, conversation",
            "target: optional string for apps, files, or model names",
            "query: optional string for searches",
            "text: optional string for note/task content",
            "seconds: optional integer duration in seconds",
            "label: optional string for timer/reminder label",
            "reminder: optional boolean",
            "model: optional string when switching models",
            "wake_word: optional string when changing wake word",
            "action: optional string for contact, security, or power actions",
            "",
            f"User text: {text}",
        ]
    )
    payload, error = request_json(prompt, model=STATE.get("model", DEFAULT_MODEL))
    if not payload or error:
        return None

    kind = normalize_text(str(payload.get("kind", "")))
    if kind not in VOICE_INTENT_KINDS:
        return None

    return payload


def execute_intent(intent: dict[str, Any]) -> dict[str, Any] | None:
    kind = normalize_text(str(intent.get("kind", "")))
    if kind == "conversation":
        return None

    if kind == "open":
        target = str(intent.get("target") or intent.get("query") or intent.get("text") or "").strip()
        if not target:
            return {"handled": True, "reply": "I need a target to open.", "kind": "open"}
        return {"handled": True, "reply": open_target(target), "kind": "open"}

    if kind == "close":
        target = str(intent.get("target") or intent.get("query") or intent.get("text") or "").strip()
        if not target:
            return {"handled": True, "reply": "I need a target to close.", "kind": "close"}
        return {"handled": True, "reply": close_target(target), "kind": "close"}

    if kind == "search":
        query = str(intent.get("query") or intent.get("target") or intent.get("text") or "").strip()
        if not query:
            return {"handled": True, "reply": "Tell me what to search for.", "kind": "search"}
        return {"handled": True, "reply": search_web(query), "kind": "search"}

    if kind in {"note", "task"}:
        content = str(intent.get("text") or intent.get("query") or intent.get("target") or "").strip()
        if not content:
            return {"handled": True, "reply": "Give me the note text.", "kind": kind}
        if kind == "note":
            return {"handled": True, "reply": add_note(content), "kind": "note"}
        return {"handled": True, "reply": add_task(content), "kind": "task"}

    if kind in {"timer", "reminder"}:
        seconds_value = intent.get("seconds")
        try:
            seconds = int(seconds_value) if seconds_value is not None else 0
        except Exception:
            seconds = 0
        if seconds <= 0:
            label_text = str(intent.get("label") or intent.get("text") or "").strip()
            seconds = parse_duration_seconds(label_text) or 0
        label = str(intent.get("label") or intent.get("text") or "").strip() or "Reminder"
        reminder_mode = kind == "reminder" or bool(intent.get("reminder"))
        if seconds <= 0:
            return {
                "handled": True,
                "reply": "Give me a duration like 5 minutes or 30 seconds.",
                "kind": "timer",
            }
        return {
            "handled": True,
            "reply": schedule_timer(seconds, label, reminder=reminder_mode),
            "kind": "timer",
        }

    if kind == "model":
        model_name = str(intent.get("model") or intent.get("target") or intent.get("text") or "").strip()
        if not model_name:
            return {"handled": True, "reply": "Tell me which model to use.", "kind": "model"}
        ok, result = set_model(model_name)
        if ok:
            return {"handled": True, "reply": f"Preferred model set to {result}.", "kind": "model"}
        return {"handled": True, "reply": result, "kind": "model"}

    if kind == "time":
        timestamp = datetime.now().strftime("%A, %B %d, %Y %H:%M")
        return {"handled": True, "reply": timestamp, "kind": "time"}

    if kind == "metrics":
        metrics = get_system_metrics(force=True)
        return {"handled": True, "reply": format_metrics_summary(metrics), "kind": "metrics"}

    if kind == "lock":
        return {"handled": True, "reply": lock_pc(), "kind": "lock"}

    if kind == "security":
        mode = str(intent.get("action") or intent.get("target") or intent.get("text") or "").strip()
        if not mode:
            return {"handled": True, "reply": "Use normal, shield, silent, or lockdown.", "kind": "security"}
        return {"handled": True, "reply": set_security_mode(mode), "kind": "security"}

    if kind == "power":
        action = str(intent.get("action") or intent.get("target") or intent.get("text") or "").strip()
        if not action:
            return {"handled": True, "reply": "Use power up, power down, sleep, restart, shutdown, hibernate, or logoff.", "kind": "power"}
        normalized_action = normalize_text(action)
        if normalized_action in {"power up", "up", "online", "resume", "wake", "power down", "down", "standby", "sleep"}:
            return {"handled": True, "reply": set_power_state(action), "kind": "power"}
        return {"handled": True, "reply": control_pc_power(action), "kind": "power"}

    if kind == "download":
        source_url = str(intent.get("target") or intent.get("query") or intent.get("text") or "").strip()
        if not source_url:
            return {"handled": True, "reply": "Give me a direct link to download.", "kind": "download"}
        return {"handled": True, "reply": download_direct_file(source_url), "kind": "download"}

    if kind == "screenshot":
        return {"handled": True, "reply": capture_screenshot(), "kind": "screenshot"}

    if kind == "contact":
        action = normalize_text(str(intent.get("action") or "call"))
        target = str(intent.get("target") or intent.get("query") or intent.get("text") or "").strip()
        if not target:
            return {"handled": True, "reply": "Give me a contact name, phone, or email.", "kind": "contact"}
        if action == "message":
            return {"handled": True, "reply": message_contact(target), "kind": "contact"}
        return {"handled": True, "reply": call_contact(target), "kind": "contact"}

    if kind == "vision":
        return {"handled": True, "reply": camera_face_status(), "kind": "vision"}

    if kind == "owner":
        owner_name = STATE.get("owner_name", OWNER_NAME)
        return {"handled": True, "reply": f"You are {owner_name}, {OWNER_TITLE}.", "kind": "owner"}

    if kind == "wake_word":
        wake_word = str(intent.get("wake_word") or intent.get("target") or intent.get("text") or "").strip().lower()
        if not wake_word:
            return {"handled": True, "reply": "Wake word is required.", "kind": "wake_word"}
        STATE["wake_word"] = wake_word
        touch_state()
        rebuild_memory_summary()
        save_state()
        return {"handled": True, "reply": f"Wake word set to {STATE['wake_word']}.", "kind": "wake_word"}

    if kind == "clear_memory":
        return {"handled": True, "reply": "Memory cleared.", "kind": "memory", "state": clear_state()}

    return None


def build_ai_context() -> str:
    metrics = get_system_metrics()
    return "\n".join(
        [
            f"System: {STATE.get('name', 'FRIDAY')}",
            f"Owner: {STATE.get('owner_name', OWNER_NAME)} ({STATE.get('owner_title', OWNER_TITLE)})",
            f"Wake word: {STATE.get('wake_word', 'hey friday')}",
            f"Preferred model: {STATE.get('model', DEFAULT_MODEL)}",
            f"Memory summary: {STATE.get('memory_summary', 'No stored memory yet.')}",
            f"Learned facts: {format_fact_list()}",
            f"Telemetry: {format_metrics_summary(metrics)}",
            f"Open tasks: {format_task_list()}",
            f"Notes: {format_note_list()}",
            f"Capabilities: {smart_capabilities()}",
            f"Security mode: {STATE.get('security_mode', 'normal')}",
            f"Power state: {STATE.get('power_state', 'online')}",
        ]
    )


def handle_message(text: str, source: str = "typed") -> dict[str, Any]:
    record_history("user", text)
    record_command_memory(text, source)
    routed = route_command(text, source=source)
    if routed["handled"]:
        reply = routed["reply"]
        if reply:
            record_history("friday", reply)
            record_event(routed["kind"], reply)
            rebuild_memory_summary()
            save_state()
        return {
            "reply": reply,
            "handled": True,
            "kind": routed["kind"],
            "state": public_state(),
        }

    if normalize_text(source) == "voice":
        intent = classify_voice_intent(text)
        if intent:
            executed = execute_intent(intent)
            if executed:
                reply = executed.get("reply", "")
                if reply:
                    record_history("friday", reply)
                    record_event(executed["kind"], reply)
                    rebuild_memory_summary()
                    save_state()
                return {
                    "reply": reply,
                    "handled": True,
                    "kind": executed["kind"],
                    "state": public_state(),
                }

    reply, error = generate_reply(
        text,
        history=STATE.get("history", []),
        context=build_ai_context(),
        model=STATE.get("model", DEFAULT_MODEL),
    )
    if not reply:
        reply = "FRIDAY is ready, but the cloud model is not connected."
    record_history("friday", reply)
    record_event("conversation", reply)
    rebuild_memory_summary()
    save_state()
    return {
        "reply": reply,
        "handled": False,
        "kind": "conversation",
        "error": error,
        "state": public_state(),
    }


def clear_state() -> dict[str, Any]:
    STATE["history"] = []
    STATE["events"] = []
    STATE["notes"] = []
    STATE["tasks"] = []
    STATE["facts"] = []
    STATE["command_memory"] = []
    STATE["memory_summary"] = "No stored memory yet."
    touch_state()
    save_state()
    return public_state()


def serve_file(handler: BaseHTTPRequestHandler, path: Path, content_type: str) -> None:
    if not path.exists():
        handler.send_error(404)
        return
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Expires", "0")
    handler.end_headers()
    handler.wfile.write(body)


class FridayHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/":
            return serve_file(self, INDEX_FILE, "text/html; charset=utf-8")
        if self.path == "/app.css":
            return serve_file(self, STYLE_FILE, "text/css; charset=utf-8")
        if self.path == "/app.js":
            return serve_file(self, SCRIPT_FILE, "application/javascript; charset=utf-8")
        if self.path == "/api/health":
            return self._send_json(
                {
                    "status": "online",
                    "name": STATE.get("name", "FRIDAY"),
                    "model": STATE.get("model", DEFAULT_MODEL),
                    "cloud_ready": openai_ready(),
                    "wake_word": STATE.get("wake_word", "hey friday"),
                    "timestamp": now_iso(),
                }
            )
        if self.path == "/api/state":
            return self._send_json(public_state())
        if self.path == "/api/metrics":
            return self._send_json(get_system_metrics(force=False))
        if self.path == "/api/models":
            return self._send_json({"supported_models": list(SUPPORTED_MODELS), "preferred": STATE.get("model", DEFAULT_MODEL)})
        if self.path == "/favicon.ico":
            return self._send_text("", status=204)
        self.send_error(404)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""

        if self.path == "/api/chat":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            text = str(payload.get("text", "")).strip()
            source = str(payload.get("source") or "typed").strip() or "typed"
            if not text:
                return self._send_json({"ok": False, "error": "Empty message."}, status=400)
            result = handle_message(text, source=source)
            return self._send_json({"ok": True, **result})

        if self.path == "/api/transcribe":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            audio_value = payload.get("audio_base64") or payload.get("audio") or ""
            model = str(payload.get("model") or "").strip() or None
            try:
                audio_bytes = decode_audio_payload(audio_value)
                text, error = transcribe_audio_bytes(audio_bytes, model=model)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            response = {"ok": True, "text": text, "state": public_state()}
            if error and not text:
                response["error"] = error
            return self._send_json(response)

        if self.path == "/api/note":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            reply = add_note(str(payload.get("text", "")))
            return self._send_json({"ok": True, "reply": reply, "state": public_state()})

        if self.path == "/api/task":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            reply = add_task(str(payload.get("text", "")))
            return self._send_json({"ok": True, "reply": reply, "state": public_state()})

        if self.path == "/api/task/complete":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            reply = complete_task(str(payload.get("target", "")))
            return self._send_json({"ok": True, "reply": reply, "state": public_state()})

        if self.path == "/api/model":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            model = str(payload.get("model", "")).strip()
            ok, result = set_model(model)
            if not ok:
                return self._send_json({"ok": False, "error": result}, status=400)
            return self._send_json({"ok": True, "model": result, "state": public_state()})

        if self.path == "/api/wake-word":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            wake_word = str(payload.get("wake_word", "")).strip().lower()
            if not wake_word:
                return self._send_json({"ok": False, "error": "Wake word is required."}, status=400)
            STATE["wake_word"] = wake_word
            touch_state()
            rebuild_memory_summary()
            save_state()
            record_event("wake_word", f"Wake word set to {wake_word}.")
            save_state()
            return self._send_json({"ok": True, "wake_word": wake_word, "state": public_state()})

        if self.path == "/api/clear":
            return self._send_json({"ok": True, "state": clear_state()})

        if self.path == "/api/file/summarize":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            path_text = str(payload.get("path", "")).strip()
            if not path_text:
                return self._send_json({"ok": False, "error": "File path is required."}, status=400)
            reply = summarize_document(path_text)
            return self._send_json({"ok": True, "reply": reply, "state": public_state()})

        if self.path == "/api/file/read":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            path_text = str(payload.get("path", "")).strip()
            content, error = read_text_file(path_text)
            if error:
                return self._send_json({"ok": False, "error": error}, status=400)
            return self._send_json({"ok": True, "content": content, "state": public_state()})

        if self.path == "/api/open":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            target = str(payload.get("target", "")).strip()
            return self._send_json({"ok": True, "reply": open_target(target), "state": public_state()})

        if self.path == "/api/close":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            target = str(payload.get("target", "")).strip()
            return self._send_json({"ok": True, "reply": close_target(target), "state": public_state()})

        if self.path == "/api/search":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            query = str(payload.get("query", "")).strip()
            return self._send_json({"ok": True, "reply": search_web(query), "state": public_state()})

        if self.path == "/api/timer":
            try:
                payload = parse_json_body(raw_body)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=400)
            duration = int(payload.get("seconds") or 0)
            label = str(payload.get("label", "")).strip()
            reminder = bool(payload.get("reminder"))
            if duration <= 0:
                return self._send_json({"ok": False, "error": "Timer duration is required."}, status=400)
            reply = schedule_timer(duration, label or "Timer", reminder=reminder)
            return self._send_json({"ok": True, "reply": reply, "state": public_state()})

        self.send_error(404)


def open_browser() -> None:
    time.sleep(1.2)
    webbrowser.open(LOCAL_URL)


def ensure_state_file() -> None:
    global STATE
    with STATE_LOCK:
        STATE = load_state()
        if not STATE_FILE.exists():
            _write_state_file_locked()
        else:
            rebuild_memory_summary()
            _write_state_file_locked()


def main() -> None:
    ensure_state_file()
    if AUTO_OPEN_BROWSER:
        threading.Thread(target=open_browser, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), FridayHandler)
    print(f"FRIDAY running at {LOCAL_URL}")
    print(f"Preferred model: {STATE.get('model', DEFAULT_MODEL)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
