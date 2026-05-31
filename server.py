from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import webbrowser
from copy import deepcopy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from friday_ai import DEFAULT_MODEL, SUPPORTED_MODELS, generate_reply, openai_ready, resolve_model

HOST = os.getenv("FRIDAY_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
LOCAL_URL = f"http://127.0.0.1:{PORT}"
AUTO_OPEN_BROWSER = os.getenv("FRIDAY_AUTO_OPEN", "1").lower() not in {"0", "false", "no"}

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "friday_state.json"
INDEX_FILE = BASE_DIR / "index.html"
STYLE_FILE = BASE_DIR / "app.css"
SCRIPT_FILE = BASE_DIR / "app.js"

STATE_LOCK = threading.Lock()
METRICS_LOCK = threading.Lock()
METRICS_CACHE: dict[str, Any] = {"timestamp": 0.0, "data": {}}
STATE: dict[str, Any] = {}

MAX_HISTORY = 40
MAX_EVENTS = 20
MAX_NOTES = 24
MAX_TASKS = 24

APP_ALIASES = {
    "settings": "ms-settings:",
    "system settings": "ms-settings:",
    "display settings": "ms-settings:display",
    "sound settings": "ms-settings:sound",
    "network settings": "ms-settings:network",
    "bluetooth settings": "ms-settings:bluetooth",
    "privacy settings": "ms-settings:privacy",
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

SETTINGS_ALIASES = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "network": "ms-settings:network",
    "bluetooth": "ms-settings:bluetooth",
    "privacy": "ms-settings:privacy",
    "apps": "ms-settings:appsfeatures",
    "power": "ms-settings:powersleep",
    "about": "ms-settings:about",
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
        "wake_word": "hey friday",
        "model": model,
        "cloud_ready": openai_ready(),
        "memory_summary": "No stored memory yet.",
        "history": [],
        "events": [],
        "notes": [],
        "tasks": [],
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
                "detail": "Local machine actions",
            },
            {
                "name": "Analytics",
                "status": "Live",
                "detail": "CPU, GPU, RAM, network, and battery",
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
                "wake_word",
                "model",
                "cloud_ready",
                "memory_summary",
                "history",
                "events",
                "notes",
                "tasks",
                "modules",
                "created_at",
            ):
                if key in raw:
                    state[key] = raw[key]
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


def build_memory_summary() -> str:
    notes = [item["text"] for item in STATE.get("notes", [])[-5:]]
    tasks = [item["text"] for item in STATE.get("tasks", []) if not item.get("done")][:5]
    replies = [item["text"] for item in STATE.get("history", []) if item.get("role") == "friday"][-3:]
    parts: list[str] = []
    if notes:
        parts.append(f"Notes: {', '.join(notes)}")
    if tasks:
        parts.append(f"Open tasks: {', '.join(tasks)}")
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
    return payload


def parse_json_body(raw_body: bytes) -> dict[str, Any]:
    if not raw_body:
        return {}
    data = json.loads(raw_body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


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


def build_context() -> str:
    metrics = get_system_metrics()
    return "\n".join(
        [
            f"System name: {STATE.get('name', 'FRIDAY')}",
            f"Wake word: {STATE.get('wake_word', 'hey friday')}",
            f"Preferred model: {STATE.get('model', DEFAULT_MODEL)}",
            f"Memory summary: {STATE.get('memory_summary', 'No stored memory yet.')}",
            f"Notes: {format_note_list()}",
            f"Open tasks: {format_task_list()}",
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
    for item in tasks:
        if lowered == item.get("id") or lowered == normalize_text(item.get("text", "")):
            item["done"] = True
            rebuild_memory_summary()
            record_event("task", f"Completed task: {item['text']}")
            save_state()
            return f"Marked complete: {item['text']}"
    return "I could not find that task."


def open_target(target: str) -> str:
    cleaned = target.strip().strip('"').strip("'")
    if not cleaned:
        return "I need a target to open."
    lookup = APP_ALIASES.get(cleaned.lower(), cleaned)
    if lookup.startswith(("http://", "https://", "ms-settings:", "steam://")):
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


def open_settings(section: str | None = None) -> str:
    if section:
        target = SETTINGS_ALIASES.get(normalize_text(section), "ms-settings:")
    else:
        target = "ms-settings:"
    try:
        os.startfile(target)
    except Exception:
        webbrowser.open(target)
    return f"Opening settings for {section or 'system'}."


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


def route_command(raw_text: str) -> dict[str, Any]:
    original = (raw_text or "").strip()
    text = strip_wake_word(original)
    lowered = normalize_text(text)
    if not lowered:
        return {"handled": True, "reply": "Online.", "kind": "greeting"}

    if lowered in {"hi", "hello", "hey", "good morning", "good evening", "good night"}:
        return {"handled": True, "reply": "Online and ready.", "kind": "greeting"}

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
        STATE["memory_summary"] = "No stored memory yet."
        touch_state()
        save_state()
        return {"handled": True, "reply": "Memory cleared.", "kind": "memory"}

    if lowered.startswith(("open settings", "open system settings", "settings")):
        section = None
        if "display" in lowered:
            section = "display"
        elif "sound" in lowered:
            section = "sound"
        elif "network" in lowered:
            section = "network"
        elif "bluetooth" in lowered:
            section = "bluetooth"
        elif "privacy" in lowered:
            section = "privacy"
        return {"handled": True, "reply": open_settings(section), "kind": "open"}

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


def build_ai_context() -> str:
    metrics = get_system_metrics()
    return "\n".join(
        [
            f"System: {STATE.get('name', 'FRIDAY')}",
            f"Wake word: {STATE.get('wake_word', 'hey friday')}",
            f"Preferred model: {STATE.get('model', DEFAULT_MODEL)}",
            f"Memory summary: {STATE.get('memory_summary', 'No stored memory yet.')}",
            f"Telemetry: {format_metrics_summary(metrics)}",
            f"Open tasks: {format_task_list()}",
            f"Notes: {format_note_list()}",
        ]
    )


def handle_message(text: str) -> dict[str, Any]:
    record_history("user", text)
    routed = route_command(text)
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
            if not text:
                return self._send_json({"ok": False, "error": "Empty message."}, status=400)
            result = handle_message(text)
            return self._send_json({"ok": True, **result})

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
