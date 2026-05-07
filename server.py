import base64
import html
import io
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote_plus

from friday_ai import ai_enabled, request_json

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

try:
    import face_recognition
except Exception:
    face_recognition = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

HOST = "0.0.0.0"
PORT = 5000
LOCAL_URL = f"http://127.0.0.1:{PORT}"
BASE_DIR = Path(__file__).resolve().parent
KNOWN_FACES_DIR = BASE_DIR / "known_faces"
KNOWN_FACES_DIR.mkdir(exist_ok=True)
CAPTURE_DIR = BASE_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
USERS_FILE = BASE_DIR / "family_users.json"
MEMORY_FILE = BASE_DIR / "web_memory.json"

SESSIONS = {}
KNOWN_FACE_ENCODINGS = []
KNOWN_FACE_NAMES = []
STATE_LOCK = threading.Lock()
ACTIVITY_PASSWORD = "Friday"

DEFAULT_USERS = {
    "owner": {
        "display_name": "You",
        "assistant_name": "F.R.I.D.A.Y.",
        "password": "fy",
        "language": "en",
        "banned": False,
        "is_admin": True,
    },
    "senan": {
        "display_name": "Senan",
        "assistant_name": "J.A.R.V.I.S.",
        "password": "JS",
        "language": "en",
        "banned": False,
        "is_admin": True,
    },
    "nazile": {
        "display_name": "Nazile",
        "assistant_name": "B.A.B.Y",
        "password": "by",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
    "vusale": {
        "display_name": "Vusale",
        "assistant_name": "K.E.N.A.N",
        "password": "Kn",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
    "novruz": {
        "display_name": "Novruz",
        "assistant_name": "Z.E.H.R.A",
        "password": "Za",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
    "zehra": {
        "display_name": "Zehra",
        "assistant_name": "S.I.R.I",
        "password": "sr",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
    "arzu": {
        "display_name": "Arzu",
        "assistant_name": "N.I.K.O",
        "password": "No",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
    "qadir": {
        "display_name": "Qadir",
        "assistant_name": "S.E.N.A.N",
        "password": "Sn",
        "language": "az",
        "banned": False,
        "is_admin": False,
    },
}

CONTACTS = {
    "mama": "+994517797733",
    "mom": "+994517797733",
    "ana": "+994517797733",
    "ata": "+994502884989",
    "dad": "+994502884989",
    "baba": "+994103830385",
    "grandpa": "+994103830385",
    "arzu": "+994773127259",
    "sister": "+994773127259",
    "nene": "+994515160683",
    "grandma": "+994515160683",
}

TEXT = {
    "en": {
        "login_title": "Private family access only.",
        "wrong_password": "Wrong password.",
        "blocked": "Access blocked. You are banned by F.R.I.D.A.Y.",
        "subtitle": "Private family console unlocked",
        "logout": "Log out",
        "camera_live": "Live Camera",
        "camera_live_sub": "Your private webcam feed is active here.",
        "camera_photo": "Photo Camera",
        "camera_photo_sub": "Choose a photo to check who is in front of the camera.",
        "unknown": "WARNING: Unknown Person Detected.",
        "known": 'His Name is "{name}"',
        "voice_title": "Voice + Command Center",
        "voice_sub": "Use the mic, talk to your assistant, or type commands as backup.",
        "mic": "Microphone",
        "talk": "Talk-to-FRIDAY",
        "voice_default": "Voice transcript will appear here.",
        "placeholder": "Ask F.R.I.D.A.Y. for anything...",
        "waiting": "Ready for your next request.",
        "send": "Send Command",
        "commands": "Example Prompts",
        "commands_sub": "Examples only. Ask naturally and F.R.I.D.A.Y. will try to turn it into actions.",
        "links": "Links",
        "local_link": "Local link",
        "family_link": "Family Wi-Fi link",
        "public_link": "Public link",
        "owner_panel": "Owner Control",
        "owner_sub": "Ban or unban any family member with one click.",
        "ban": "Ban",
        "unban": "Unban",
        "active": "Active",
        "banned": "Banned",
        "voice_unsupported": "Voice recognition is not supported in this browser.",
        "voice_listening": "Listening...",
        "voice_error": "Microphone error or permission denied.",
        "voice_empty": "No voice heard yet.",
        "voice_live": "Always listening is on.",
        "stop_listening": "Stop Listening",
        "use_mic_first": "Use the microphone first.",
        "missing_command": "Enter a command first.",
        "sending": "Sending...",
        "camera_error": "Camera unavailable or permission denied.",
        "updated": "Status updated.",
        "open_google": "Open Google",
        "take_screenshot": "Take Screenshot",
        "lock_pc": "Lock PC",
        "morning_mode": "Morning Mode",
        "privacy_mode": "Privacy Mode",
        "who_here_unknown": "No one recognized yet.",
    },
    "az": {
        "login_title": "Sexsi aile girisi.",
        "wrong_password": "Sifre yanlisdir.",
        "blocked": "Giris baglanib. Seni sahib qadaga edib.",
        "subtitle": "Sexsi aile paneli acildi",
        "logout": "Cixis",
        "camera_live": "Canli Kamera",
        "camera_live_sub": "Senin sexsi kamera goruntun burada aciqdir.",
        "camera_photo": "Foto Kamera",
        "camera_photo_sub": "Kameranin qarsisinda kimin oldugunu yoxlamaq ucun sekil sec.",
        "unknown": "WARNING: Unknown Person Detected.",
        "known": 'His Name is "{name}"',
        "voice_title": "Ses + Komanda Merkezi",
        "voice_sub": "Mikrofondan istifade et, assistentle danis, ya da komanda yaz.",
        "mic": "Mikrofon",
        "talk": "Assistentle Danis",
        "voice_default": "Ses metni burada gorunecek.",
        "placeholder": "F.R.I.D.A.Y.-dan istediyini iste...",
        "waiting": "Yeni istek ucun hazirdir.",
        "send": "Komandani Gonder",
        "commands": "Numune Istekler",
        "commands_sub": "Bunlar yalniz numunelerdir. Tebii danis, F.R.I.D.A.Y. onu hereketlere cevirmeye calisacaq.",
        "links": "Linkler",
        "local_link": "Lokal link",
        "family_link": "Aile Wi-Fi linki",
        "public_link": "Paylasilan link",
        "owner_panel": "Sahib Paneli",
        "owner_sub": "Bir klikle aile uzvlerini qadaga et ve ya ac.",
        "ban": "Qadaga Et",
        "unban": "Ac",
        "active": "Aktiv",
        "banned": "Qadagadadir",
        "voice_unsupported": "Bu brauzerde ses tanima desteklenmir.",
        "voice_listening": "Dinleyir...",
        "voice_error": "Mikrofon xetasi ve ya icaze verilmedi.",
        "voice_empty": "Hele ses esidilmedi.",
        "voice_live": "Daimi dinleme aktivdir.",
        "stop_listening": "Dinlemeyi Dayandir",
        "use_mic_first": "Evvelce mikrofonu istifade et.",
        "missing_command": "Evvelce komanda yaz.",
        "sending": "Gonderilir...",
        "camera_error": "Kamera yoxdur ve ya icaze verilmedi.",
        "updated": "Status yenilendi.",
        "open_google": "Google Ac",
        "take_screenshot": "Ekran Sekli Al",
        "lock_pc": "PC Kilidle",
        "morning_mode": "Seher Rejimi",
        "privacy_mode": "Mexfilik Rejimi",
        "who_here_unknown": "Hele hech kim taninmayib.",
    },
}

COMMAND_SPECS = [
    {
        "command": "Open Spotify and start a 20 minute focus timer",
        "natural": "launch spotify, set a timer for 20 minutes, and remind me to get back to work",
        "pc_only": True,
    },
    {
        "command": "Search the web without exact wording",
        "natural": "search for tomorrow's weather in Baku and tell me what to wear",
    },
    {
        "command": "Open sites and apps naturally",
        "natural": "open github.com, launch discord, and then open the friday site",
        "pc_only": True,
    },
    {
        "command": "Use memory like a real assistant",
        "natural": "remember my favorite game is minecraft and tell me later what you know about it",
    },
    {
        "command": "Chain security actions together",
        "natural": "turn on security mode, take a screenshot, and lock the pc",
        "pc_only": True,
    },
    {
        "command": "Ask everyday questions",
        "natural": "what time is it, what day is it, or give me the weekly forecast",
    },
    {
        "command": "Mix reminders with contacts",
        "natural": "message dad and remind me to study in 30 minutes",
    },
    {
        "command": "Use FRIDAY like a browser co-pilot",
        "natural": "open youtube, search for python tutorials, and save a reminder for later",
    },
]

SAFE_PROCESSES = {
    "System Idle Process",
    "System",
    "Registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "dwm.exe",
    "explorer.exe",
    "svchost.exe",
    "ShellExperienceHost.exe",
    "StartMenuExperienceHost.exe",
    "RuntimeBroker.exe",
    "SearchHost.exe",
    "sihost.exe",
    "fontdrvhost.exe",
    "taskhostw.exe",
    "spoolsv.exe",
    "SecurityHealthService.exe",
    "WmiPrvSE.exe",
    "audiodg.exe",
    "Code.exe",
    "python.exe",
    "pythonw.exe",
    "powershell.exe",
    "cmd.exe",
    "WindowsTerminal.exe",
}

APP_ALIASES = {
    "spotify": ["spotify"],
    "discord": ["discord"],
    "roblox": ["roblox"],
    "minecraft": ["minecraft"],
}

WEBSITE_ALIASES = {
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "netflix": "https://netflix.com",
    "classroom": "https://classroom.google.com",
    "google classroom": "https://classroom.google.com",
}

PLAN_COMMAND_LIMIT = 4

PUBLIC_URL_FILE_CANDIDATES = [BASE_DIR / "public_url.txt", BASE_DIR / "ngrok_url.txt"]


def ensure_users():
    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps(DEFAULT_USERS, indent=2), encoding="utf-8")


def load_users():
    ensure_users()
    users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    changed = False
    for key, value in DEFAULT_USERS.items():
        if key not in users:
            users[key] = value
            changed = True
            continue
        for subkey, subvalue in value.items():
            if subkey not in users[key]:
                users[key][subkey] = subvalue
                changed = True
    if changed:
        USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")
    return users


def ensure_memory():
    if not MEMORY_FILE.exists():
        payload = {}
        for user_id, data in DEFAULT_USERS.items():
            payload[user_id] = {
                "wake_word": data["assistant_name"].lower().replace(".", ""),
                "memory": {},
                "custom_commands": {
                    "chill mode": "open spotify",
                    "focus mode": "study mode",
                },
                "notifications": [],
                "messages": [],
                "activity_log": [],
                "security_mode": False,
                "last_person": {"status": "unknown", "name": ""},
                "tutorial_seen": False,
            }
        MEMORY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_memory():
    ensure_memory()
    memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    changed = False
    for user_id, data in DEFAULT_USERS.items():
        if user_id not in memory:
            memory[user_id] = {
                "wake_word": data["assistant_name"].lower().replace(".", ""),
                "memory": {},
                "custom_commands": {
                    "chill mode": "open spotify",
                    "focus mode": "study mode",
                },
                "notifications": [],
                "messages": [],
                "activity_log": [],
                "security_mode": False,
                "last_person": {"status": "unknown", "name": ""},
                "tutorial_seen": False,
            }
            changed = True
            continue
        memory[user_id].setdefault(
            "wake_word", data["assistant_name"].lower().replace(".", "")
        )
        memory[user_id].setdefault("memory", {})
        memory[user_id].setdefault("custom_commands", {})
        memory[user_id].setdefault("notifications", [])
        memory[user_id].setdefault("messages", [])
        memory[user_id].setdefault("activity_log", [])
        memory[user_id].setdefault("security_mode", False)
        memory[user_id].setdefault("last_person", {"status": "unknown", "name": ""})
        if "tutorial_seen" not in memory[user_id]:
            memory[user_id]["tutorial_seen"] = False
            changed = True
    if changed:
        MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    return memory


USERS = load_users()
MEMORY = load_memory()


def save_users():
    USERS_FILE.write_text(json.dumps(USERS, indent=2), encoding="utf-8")


def save_memory():
    MEMORY_FILE.write_text(json.dumps(MEMORY, indent=2), encoding="utf-8")


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_public_url():
    for path in PUBLIC_URL_FILE_CANDIDATES:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value.startswith("http"):
                return value
    return ""


def t(lang, key, **kwargs):
    return TEXT.get(lang, TEXT["en"]).get(key, key).format(**kwargs)


def localized(user_lang, en, az):
    return en if user_lang == "en" else az


def no_store_headers():
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def normalize_command(cmd):
    cmd = cmd.lower().replace(",", " ").replace("?", " ").strip()
    fillers = [
        "friday do me a favor and",
        "friday do me a favor",
        "friday can you please",
        "friday could you please",
        "friday can you",
        "friday could you",
        "friday will you please",
        "friday will you",
        "do me a favor and",
        "do me a favor",
        "can you please",
        "could you please",
        "can you",
        "could you",
        "will you please",
        "will you",
        "please",
        "friday",
    ]
    changed = True
    while changed:
        changed = False
        for phrase in fillers:
            if cmd.startswith(phrase + " "):
                cmd = cmd[len(phrase) :].strip()
                changed = True
    return " ".join(cmd.split())


def get_theme(user_id):
    if user_id == "owner":
        return {
            "bg": "radial-gradient(circle at top, rgba(255,115,48,.18), transparent 17%), radial-gradient(circle at 82% 22%, rgba(79,213,255,.18), transparent 14%), linear-gradient(155deg,#03070e 0%,#09111d 32%,#0f2435 68%,#09111b 100%)",
            "panel": "rgba(7, 15, 24, 0.94)",
            "line": "#30506c",
            "accent": "linear-gradient(135deg,#ff7135,#57d8ff)",
            "soft": "rgba(17, 35, 52, 0.88)",
            "text": "#f3f8ff",
            "muted": "#9cb9d0",
            "code": "#07111a",
            "glow": "0 0 30px rgba(87,216,255,.18)",
            "font": "Segoe UI, Tahoma, sans-serif",
            "tag": "F.R.I.D.A.Y Protocol",
        }
    if user_id == "senan":
        return {
            "bg": "radial-gradient(circle at top, rgba(64,227,255,.16), transparent 18%), radial-gradient(circle at 18% 30%, rgba(140,255,232,.14), transparent 16%), linear-gradient(150deg,#02070d 0%,#071320 34%,#0d2230 72%,#08111a 100%)",
            "panel": "rgba(7, 16, 25, 0.95)",
            "line": "#234a65",
            "accent": "linear-gradient(135deg,#44cbff,#96ffe0)",
            "soft": "rgba(14, 32, 45, 0.9)",
            "text": "#eefaff",
            "muted": "#96b6cc",
            "code": "#081018",
            "glow": "0 0 28px rgba(68,203,255,.18)",
            "font": "Trebuchet MS, Segoe UI, sans-serif",
            "tag": "J.A.R.V.I.S Protocol",
        }
    return {
        "bg": "radial-gradient(circle at top, rgba(0,187,255,.13), transparent 21%), linear-gradient(145deg,#07121d 0%,#0a1826 32%,#00a8d9 32%,#00a8d9 37%,#db2341 37%,#db2341 42%,#13a65a 42%,#13a65a 47%,#08121d 47%,#08121d 100%)",
        "panel": "rgba(8, 22, 35, 0.95)",
        "line": "#2d5671",
        "accent": "linear-gradient(135deg,#22c6ff,#73f1c8)",
        "soft": "rgba(18, 45, 63, 0.9)",
        "text": "#eff9ff",
        "muted": "#9ab7cf",
        "code": "#08131c",
        "glow": "0 0 18px rgba(34,198,255,.14)",
        "font": "Segoe UI, Tahoma, sans-serif",
        "tag": "Azerbaijan Edition",
    }


def find_user_by_password(password):
    for user_id, user in USERS.items():
        if user["password"] == password:
            return user_id, user
    return None, None


def load_known_faces():
    KNOWN_FACE_ENCODINGS.clear()
    KNOWN_FACE_NAMES.clear()
    if face_recognition is None:
        return
    for image_path in KNOWN_FACES_DIR.iterdir():
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        try:
            image = face_recognition.load_image_file(str(image_path))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                KNOWN_FACE_ENCODINGS.append(encodings[0])
                KNOWN_FACE_NAMES.append(image_path.stem)
        except Exception:
            continue


def get_session(handler):
    raw_cookie = handler.headers.get("Cookie")
    if not raw_cookie:
        return None
    jar = cookies.SimpleCookie()
    jar.load(raw_cookie)
    item = jar.get("friday_session")
    return SESSIONS.get(item.value) if item else None


def login_page(error_text=""):
    error_html = (
        f'<div class="error">{html.escape(error_text)}</div>' if error_text else ""
    )
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FRIDAY Login</title><style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at top, rgba(255,110,55,.18), transparent 22%),radial-gradient(circle at 85% 20%, rgba(92,214,255,.18), transparent 16%),linear-gradient(145deg,#04070d,#091523 58%,#07111c);color:#edf7ff;font-family:Segoe UI,Tahoma,sans-serif}}.panel{{width:min(94vw,620px);padding:40px 36px;border-radius:30px;border:1px solid #2d4b66;background:rgba(10,22,35,.95);box-shadow:0 32px 90px rgba(0,0,0,.38)}}h1{{margin:0 0 12px;font-size:3rem;letter-spacing:.09em;font-weight:900}}p{{margin:0 0 28px;color:#b3c7db;font-size:1.06rem}}label{{display:block;margin-bottom:10px;font-size:1.05rem;font-weight:700}}input,button{{width:100%;display:block;border-radius:18px}}input{{padding:16px 18px;background:#14283c;color:#edf7ff;border:1px solid #315978;outline:none;font-size:1rem}}input:focus{{border-color:#63d8ff;box-shadow:0 0 0 3px rgba(99,216,255,.15)}}button{{margin-top:18px;padding:16px 18px;border:0;background:linear-gradient(135deg,#64d4ff,#79f4d0);font-weight:900;font-size:1rem;cursor:pointer;color:#03111b}}.error{{margin-top:18px;color:#ff9d9d;font-weight:700}}</style></head><body><form class="panel" method="post" action="/login" autocomplete="off"><h1>F.R.I.D.A.Y.</h1><p>Private family access only.</p><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="new-password" required><button type="submit">Enter</button>{error_html}</form><script>const password=document.getElementById("password");password.value="";password.focus();</script></body></html>"""
    return page.encode("utf-8")


def render_admin_panel(user_id, lang):
    if not USERS[user_id].get("is_admin"):
        return ""
    rows = []
    for member_id, member in USERS.items():
        if member_id == user_id:
            continue
        action = t(lang, "unban") if member["banned"] else t(lang, "ban")
        state = t(lang, "banned") if member["banned"] else t(lang, "active")
        rows.append(
            f'<div class="member-row"><div><strong>{html.escape(member["display_name"])}</strong><div class="small">{html.escape(member["assistant_name"])}</div></div><div><span class="badge">{html.escape(state)}</span><button class="secondary mini" onclick="toggleBan(\'{member_id}\')">{html.escape(action)}</button></div></div>'
        )
    return f'<section class="panel"><h2>{html.escape(t(lang, "owner_panel"))}</h2><p class="sub">{html.escape(t(lang, "owner_sub"))}</p>{"".join(rows)}</section>'


def render_messages_panel(user_id, lang):
    title = "Assistant Messages" if lang == "en" else "Assistent Mesajlari"
    subtitle = (
        "Latest things your assistant said."
        if lang == "en"
        else "Assistentin son dedikleri."
    )
    items = []
    for item in MEMORY[user_id].get("messages", [])[-12:]:
        role = html.escape(item.get("role", "assistant").title())
        text = html.escape(item.get("text", ""))
        stamp = html.escape(item.get("time", ""))
        items.append(
            f'<div class="message-item"><strong>{role}</strong><div class="small">{stamp}</div><div>{text}</div></div>'
        )
    if not items:
        items.append(
            f'<div class="message-item"><div class="small">{"No messages yet." if lang == "en" else "Hele mesaj yoxdur."}</div></div>'
        )
    return f'<section class="panel"><h2>{title}</h2><p class="sub">{subtitle}</p><div id="messageHistory">{"".join(items)}</div></section>'


def render_activity_panel(user_id, lang):
    if user_id != "owner":
        return ""
    title = ""
    subtitle = ""
    button = "Open" if lang == "en" else "Ac"
    close_text = "Close" if lang == "en" else "Bagla"
    wrong = "Wrong password." if lang == "en" else "Sifre yanlisdir."
    loading = "Loading..." if lang == "en" else "Yuklenir..."
    return f'<section class="panel"><div class="actions"><button class="secondary" id="activityButton">{button}</button></div><div id="activityWrap" class="status" style="display:none"></div><div id="activityError" class="small"></div><div class="actions" id="activityCloseWrap" style="display:none"><button class="secondary" id="activityClose">{close_text}</button></div><div id="activityMeta" data-wrong="{html.escape(wrong)}" data-loading="{html.escape(loading)}"></div></section>'


def render_abilities_panel(user_id, lang):
    abilities = [
        "Natural-language requests",
        "AI command planning",
        "Multi-step actions",
        "Camera and face status",
        "Typed commands",
        "Assistant voice replies",
        "Command memory",
        "Timers and reminders",
        "Call/message contacts",
        "Security mode controls",
        "MP4 direct-link downloader",
    ]
    if user_id in {"owner", "senan"}:
        abilities.extend(["PC controls", "Screenshot tools", "Desktop app launchers"])
    if not ai_enabled():
        abilities.append("Fallback rule-based mode only until AI is configured")
    items = "".join(
        f'<div class="message-item">{html.escape(item)}</div>' for item in abilities
    )
    title = "What FRIDAY Can Do" if lang == "en" else "FRIDAY Ne Ede Biler"
    subtitle = (
        "Built-in abilities plus open-ended action planning."
        if lang == "en"
        else "Daxili bacariqlar ve aciq uclu hereket planlamasi."
    )
    return f'<section class="panel"><h2>{title}</h2><p class="sub">{subtitle}</p>{items}</section>'


def render_download_panel(lang):
    title = "MP4 Downloader" if lang == "en" else "MP4 Yukleyici"
    subtitle = (
        "Paste a direct .mp4 link." if lang == "en" else "Birbasa .mp4 linki daxil et."
    )
    placeholder = "https://example.com/video.mp4"
    button = "Download MP4" if lang == "en" else "MP4 Yukle"
    return f'<section class="panel"><h2>{title}</h2><p class="sub">{subtitle}</p><input id="mp4Url" type="text" placeholder="{placeholder}" style="width:100%;padding:12px 14px;border-radius:14px;border:1px solid #33556f;background:rgba(13,30,44,.8);color:inherit"><div class="actions"><button class="secondary" id="downloadMp4Button">{button}</button></div></section>'


def render_tutorial_panel(user_id, lang):
    assistant = USERS[user_id]["assistant_name"]
    title = "Tutorial" if lang == "en" else "Telim"
    subtitle = (
        "Learn the basics of your assistant."
        if lang == "en"
        else "Assistentinin esaslarini oyren."
    )
    button = "Open Tutorial" if lang == "en" else "Telimi Ac"
    close = "Hide Tutorial" if lang == "en" else "Telimi Gizlet"
    steps = [
        (
            f"1. Use {assistant} with the microphone or by typing commands."
            if lang == "en"
            else f"1. {assistant} ile mikrofonla ve ya komanda yazaraq danis."
        ),
        (
            "2. The microphone starts always-listening mode after one click."
            if lang == "en"
            else "2. Mikrofon bir klikden sonra daimi dinleme rejimine kecir."
        ),
        (
            "3. Use camera actions like take picture, start recording, and scanning."
            if lang == "en"
            else "3. Sekil cekmek, qeydiyyata baslamaq ve scan etmek ucun kamera hereketlerinden istifade et."
        ),
        (
            "4. The Example Prompts section gives ideas, not limits."
            if lang == "en"
            else "4. Numune Istekler hissesi yalniz ideya verir, limit qoymur."
        ),
        (
            "5. Ask naturally, even if your wording changes."
            if lang == "en"
            else "5. Ifadeni deyissen bele tebii sekilde isteyini de."
        ),
    ]
    items = "".join(
        f'<div class="message-item">{html.escape(step)}</div>' for step in steps
    )
    return f'<section class="panel"><div class="actions"><button class="secondary" id="tutorialButton">{html.escape(button)}</button><button class="secondary" id="tutorialClose" style="display:none">{html.escape(close)}</button></div><div id="tutorialWrap" style="display:none"><h2>{html.escape(title)}</h2><p class="sub">{html.escape(subtitle)}</p>{items}</div></section>'


def command_cards_for(user_id):
    allow_pc_controls = user_id in {"owner", "senan"}
    cards = []
    for spec in COMMAND_SPECS:
        if spec.get("pc_only") and not allow_pc_controls:
            continue
        cards.append(
            f'<div class="command-card"><strong>{html.escape(spec["command"])}</strong><div class="small">{html.escape(spec["natural"])}</div></div>'
        )
    return "".join(cards)


def control_page(user_id):
    user = USERS[user_id]
    lang = user["language"]
    theme = get_theme(user_id)
    show_live_camera = user_id == "owner"
    allow_pc_lock = user_id in {"owner", "senan"}
    family_url = f"http://{get_local_ip()}:{PORT}"
    public_url = get_public_url()
    memory = MEMORY[user_id]
    admin_panel = render_admin_panel(user_id, lang)
    tutorial_panel = render_tutorial_panel(user_id, lang)
    show_tutorial = not memory.get("tutorial_seen", False)

    css = """*{box-sizing:border-box}
body{margin:0;background:__BG__;color:__TEXT__;font-family:__FONT__;padding:24px;overflow-x:hidden;position:relative}

/* 🔵 HUD GRID */
.hud-grid{
position:fixed;inset:0;pointer-events:none;
background-image:
linear-gradient(rgba(0,180,255,.08) 1px,transparent 1px),
linear-gradient(90deg,rgba(0,180,255,.08) 1px,transparent 1px);
background-size:40px 40px;
animation:gridMove 12s linear infinite;
z-index:9999
}
@keyframes gridMove{
from{background-position:0 0}
to{background-position:40px 40px}
}

/* 🎯 TARGET LOCK */
.target-lock{
position:fixed;width:80px;height:80px;
border:2px solid #00ccff;border-radius:12px;
pointer-events:none;transform:translate(-50%,-50%);
box-shadow:0 0 20px rgba(0,200,255,.9);
z-index:10000
}

/* 👁️ SCAN LINE */
.scan-line{
position:fixed;left:0;width:100%;height:2px;
background:linear-gradient(90deg,transparent,#00ccff,transparent);
animation:scanMove 3s linear infinite;
z-index:9998
}
@keyframes scanMove{
0%{top:0%;opacity:0}
50%{opacity:1}
100%{top:100%;opacity:0}
}

/* 🧠 THINKING DOTS */
.thinking span{
opacity:0;
animation:thinking 1.4s infinite
}
.thinking span:nth-child(2){animation-delay:.2s}
.thinking span:nth-child(3){animation-delay:.4s}
@keyframes thinking{
0%,80%,100%{opacity:0}
40%{opacity:1}
}

/* ⚡ VOICE MODE */
.voice-active{
box-shadow:0 0 40px #00ccff inset,0 0 80px #00ccff
}

/* 💠 PANEL HOLOGRAM */
.panel{
padding:24px;position:relative;overflow:hidden;
background:__PANEL__;border:1px solid __LINE__;
border-radius:24px;box-shadow:0 24px 80px rgba(0,0,0,.34)
}
.panel:before{
content:"";position:absolute;inset:0;
background:linear-gradient(120deg,transparent,rgba(0,200,255,.08),transparent);
animation:shimmer 4s infinite
}
@keyframes shimmer{
0%{transform:translateX(-100%)}
100%{transform:translateX(100%)}
}

/* ===== ORIGINAL UI ===== */
.wrap{max-width:1320px;margin:0 auto}
.top{padding:20px 22px;display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px;position:relative;overflow:hidden;background:__PANEL__;border:1px solid __LINE__;border-radius:24px;box-shadow:0 24px 80px rgba(0,0,0,.34)}
.top:before{content:"";position:absolute;left:0;top:0;width:100%;height:4px;background:__ACCENT__}
.hero{font-size:2rem;font-weight:900;letter-spacing:.16em;text-transform:uppercase;text-shadow:__GLOW__}
.tag{display:inline-block;margin-top:8px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.05);color:__MUTED__;font-size:.9rem}
.logout{color:__TEXT__;text-decoration:none;border:1px solid __LINE__;padding:11px 16px;border-radius:12px}
.grid{display:grid;grid-template-columns:1.15fr .85fr;gap:24px}
.stack{display:grid;gap:24px}
.camera-box{width:100%;aspect-ratio:16/10;background:#03111b;border-radius:18px;overflow:hidden;border:1px solid __LINE__;display:grid;place-items:center}
video,img{width:100%;height:100%;object-fit:cover}
h2{margin:0 0 8px;font-size:1.22rem}
.sub,.small{color:__MUTED__}
.small{font-size:.95rem}
.status,.voicebox,.link-box,.member-row,.command-card,.photo-wrap,.notice{margin-top:12px;padding:13px 14px;border-radius:16px;background:__SOFT__;border:1px solid __LINE__}
.voicebox{min-height:52px;white-space:pre-wrap}
.notice{background:rgba(255,158,88,.12);border-color:rgba(255,158,88,.45)}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}
button{border:0;border-radius:15px;padding:12px 16px;background:__ACCENT__;font-weight:900;cursor:pointer;color:#03111b}
.secondary{background:__SOFT__;color:__TEXT__;border:1px solid __LINE__}
.mini{padding:8px 12px;margin-left:8px}
textarea{width:100%;min-height:130px;background:__SOFT__;color:__TEXT__;border:1px solid __LINE__;border-radius:16px;padding:14px;resize:vertical}
.row2{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap}
.command-grid{display:grid;gap:12px}
.message-item{margin-top:12px;padding:13px 14px;border-radius:16px;background:__SOFT__;border:1px solid __LINE__}
.member-row{display:flex;justify-content:space-between;align-items:center;gap:12px}
.badge{display:inline-block;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.06);color:__MUTED__;margin-right:8px}
code{display:block;margin-top:6px;padding:10px;border-radius:12px;background:__CODE__;color:__TEXT__;word-break:break-all}
input[type=file]{width:100%;color:__TEXT__}
@media (max-width:1000px){.grid{grid-template-columns:1fr}.top{flex-direction:column;align-items:flex-start}}
"""
    for key, value in {
        "__BG__": theme["bg"],
        "__TEXT__": theme["text"],
        "__FONT__": theme["font"],
        "__PANEL__": theme["panel"],
        "__LINE__": theme["line"],
        "__ACCENT__": theme["accent"],
        "__GLOW__": theme["glow"],
        "__MUTED__": theme["muted"],
        "__SOFT__": theme["soft"],
        "__CODE__": theme["code"],
    }.items():
        css = css.replace(key, value)

    if show_live_camera:
        camera_section = f'<section class="panel"><h2>{html.escape(t(lang, "camera_live"))}</h2><p class="sub">{html.escape(t(lang, "camera_live_sub"))}</p><div class="camera-box"><video id="liveCamera" autoplay playsinline muted></video></div><div id="personStatus" class="status">{html.escape(t(lang, "unknown"))}</div></section>'
    else:
        camera_section = f'<section class="panel"><h2>{html.escape(t(lang, "camera_photo"))}</h2><p class="sub">{html.escape(t(lang, "camera_photo_sub"))}</p><div class="photo-wrap"><input id="photoInput" type="file" accept="image/*" capture="environment"></div><div class="camera-box"><video id="photoCamera" autoplay playsinline muted style="display:none"></video><img id="photoPreview" alt="photo preview" style="display:none"></div><div id="personStatus" class="status">{html.escape(t(lang, "unknown"))}</div></section>'

    if allow_pc_lock:
        quick_buttons = [
            f'<button class="secondary" onclick="sendPreset(\'open google\')">{html.escape(t(lang, "open_google"))}</button>',
            f'<button class="secondary" onclick="sendPreset(\'take screenshot\')">{html.escape(t(lang, "take_screenshot"))}</button>',
            f'<button class="secondary" onclick="sendPreset(\'morning mode\')">{html.escape(t(lang, "morning_mode"))}</button>',
            f'<button class="secondary" onclick="sendPreset(\'privacy mode\')">{html.escape(t(lang, "privacy_mode"))}</button>',
            f'<button class="secondary" onclick="sendPreset(\'lock pc\')">{html.escape(t(lang, "lock_pc"))}</button>',
            '<button class="secondary" onclick="sendPreset(\'enable security mode\')">Security On</button>',
            '<button class="secondary" onclick="sendPreset(\'disable security mode\')">Security Off</button>',
            '<button class="secondary" onclick="sendPreset(\'lights on\')">Lights On</button>',
            '<button class="secondary" onclick="sendPreset(\'lights off\')">Lights Off</button>',
            '<button class="secondary" onclick="sendPreset(\'enable phone viewing\')">Phone View On</button>',
            '<button class="secondary" onclick="sendPreset(\'disable phone viewing\')">Phone View Off</button>',
            '<button class="secondary" onclick="sendPreset(\'take picture\')">Take Picture</button>',
            '<button class="secondary" onclick="sendPreset(\'start recording\')">Start Recording</button>',
            '<button class="secondary" onclick="sendPreset(\'stop recording\')">Stop Recording</button>',
            '<button class="secondary" onclick="sendPreset(\'start scanning\')">Start Scanning</button>',
            '<button class="secondary" onclick="sendPreset(\'stop scanning\')">Stop Scanning</button>',
        ]
    else:
        quick_buttons = [
            '<button class="secondary" onclick="sendPreset(\'enable security mode\')">Security On</button>',
            '<button class="secondary" onclick="sendPreset(\'disable security mode\')">Security Off</button>',
            '<button class="secondary" onclick="sendPreset(\'lights on\')">Lights On</button>',
            '<button class="secondary" onclick="sendPreset(\'lights off\')">Lights Off</button>',
            '<button class="secondary" onclick="sendPreset(\'enable phone viewing\')">Phone View On</button>',
            '<button class="secondary" onclick="sendPreset(\'disable phone viewing\')">Phone View Off</button>',
            '<button class="secondary" onclick="sendPreset(\'take picture\')">Take Picture</button>',
            '<button class="secondary" onclick="sendPreset(\'start recording\')">Start Recording</button>',
            '<button class="secondary" onclick="sendPreset(\'stop recording\')">Stop Recording</button>',
            '<button class="secondary" onclick="sendPreset(\'start scanning\')">Start Scanning</button>',
            '<button class="secondary" onclick="sendPreset(\'stop scanning\')">Stop Scanning</button>',
        ]

    link_blocks = [
        f'<div class="link-box"><strong>{html.escape(t(lang, "local_link"))}</strong><code>{html.escape(LOCAL_URL)}</code></div>',
        f'<div class="link-box"><strong>{html.escape(t(lang, "family_link"))}</strong><code>{html.escape(family_url)}</code></div>',
    ]
    if public_url:
        link_blocks.append(
            f'<div class="link-box"><strong>{html.escape(t(lang, "public_link"))}</strong><code>{html.escape(public_url)}</code></div>'
        )

    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title><style>__CSS__</style></head><body><div class="wrap"><header class="top"><div><div class="hero">__ASSISTANT__</div><div class="sub">__SUBTITLE__ • __NAME__</div><div class="tag">__TAG__</div></div><a class="logout" href="/logout">__LOGOUT__</a></header><div class="grid"><div class="stack">__CAMERA_SECTION__<section class="panel"><h2>__VOICE_TITLE__</h2><p class="sub">__VOICE_SUB__</p><div class="actions"><button id="micButton">__MIC__</button><button id="talkButton">__TALK__</button><button class="secondary" id="speakButton">Hear Voice</button>__QUICK_BUTTONS__</div>__ACTIVITY_PANEL__<div id="voiceText" class="voicebox">__VOICE_DEFAULT__</div><textarea id="commandBox" placeholder="__PLACEHOLDER__"></textarea><div class="row2"><div id="resultText" class="sub">__WAITING__</div><button onclick="sendCommand()">__SEND__</button></div></section><section class="panel"><h2>__COMMANDS__</h2><p class="sub">__COMMANDS_SUB__</p><div class="command-grid">__COMMAND_CARDS__</div></section></div><div class="stack"><section class="panel"><h2>__LINKS__</h2>__LINK_BLOCKS__</section>__DOWNLOAD_PANEL__<section class="panel"><h2>Memory</h2><div class="link-box"><strong>Wake Word</strong><code>__WAKE_WORD__</code></div><div class="link-box"><strong>Known Favorite Game</strong><code>__FAVORITE_GAME__</code></div></section>__ABILITIES__ __MESSAGES__ __ADMIN__</div></div></div><script>const USER_LANG=__LANG__;const SHOW_LIVE_CAMERA=__SHOW_CAMERA__;const TEXTS=__TEXTS__;let transcriptText="";let cameraStream=null;let mediaRecorder=null;let recordingStream=null;let recordingChunks=[];let audioContext=null;let audioStream=null;let audioSource=null;let audioProcessor=null;let audioChunks=[];let audioSampleRate=44100;let alwaysListening=false;let listenTimer=null;const listenCycleMs=4000;const liveCamera=document.getElementById("liveCamera");const personStatus=document.getElementById("personStatus");const photoInput=document.getElementById("photoInput");const photoPreview=document.getElementById("photoPreview");const photoCamera=document.getElementById("photoCamera");const voiceText=document.getElementById("voiceText");const commandBox=document.getElementById("commandBox");const resultText=document.getElementById("resultText");const micButton=document.getElementById("micButton");const talkButton=document.getElementById("talkButton");const speakButton=document.getElementById("speakButton");const downloadMp4Button=document.getElementById("downloadMp4Button");const mp4Url=document.getElementById("mp4Url");const messageHistory=document.getElementById("messageHistory");const activityButton=document.getElementById("activityButton");const activityWrap=document.getElementById("activityWrap");const activityError=document.getElementById("activityError");const activityClose=document.getElementById("activityClose");const activityCloseWrap=document.getElementById("activityCloseWrap");const activityMeta=document.getElementById("activityMeta");async function postJson(url,payload){const response=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});return response.json();}async function postRaw(url,body,contentType){const response=await fetch(url,{method:"POST",headers:{"Content-Type":contentType},body});return response.json();}async function getJson(url){const response=await fetch(url);return response.json();}function setListeningUi(active){if(micButton)micButton.textContent=active?TEXTS.voice_live:TEXTS.mic;if(talkButton)talkButton.textContent=active?TEXTS.stop_listening:TEXTS.talk;if(voiceText&&!transcriptText)voiceText.textContent=active?TEXTS.voice_live:TEXTS.voice_default;}function speakAssistant(text){if(!text||!window.speechSynthesis)return;window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.lang=USER_LANG==="az"?"az-AZ":"en-US";window.speechSynthesis.speak(utterance);}function appendMessage(role,text){if(!messageHistory||!text)return;const card=document.createElement("div");card.className="message-item";const strong=document.createElement("strong");strong.textContent=role;const stamp=document.createElement("div");stamp.className="small";stamp.textContent=new Date().toLocaleTimeString();const body=document.createElement("div");body.textContent=text;card.appendChild(strong);card.appendChild(stamp);card.appendChild(body);messageHistory.prepend(card);}async function openActivityLog(){if(!activityButton||!activityWrap)return;const password=window.prompt("");if(password===null)return;activityError.textContent="";activityWrap.style.display="block";activityWrap.innerHTML=activityMeta?activityMeta.dataset.loading:"Loading...";const unlock=await postJson("/activity-unlock",{password});if(!unlock.ok){activityWrap.style.display="none";activityError.textContent=activityMeta?activityMeta.dataset.wrong:"Wrong password.";return;}const data=await getJson("/activity-log");activityWrap.innerHTML=data.html||"";activityCloseWrap.style.display="flex";}async function updateFaceStatus(imageData){try{const data=await postJson("/camera-status",{image:imageData});personStatus.textContent=data.status==="known"&&data.name?TEXTS.known.replace("{name}",data.name):TEXTS.unknown;}catch(error){personStatus.textContent=TEXTS.camera_error;}}async function startLiveCamera(){if(!SHOW_LIVE_CAMERA||!liveCamera)return;try{cameraStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});liveCamera.srcObject=cameraStream;setInterval(sendLiveFrame,3000);}catch(error){personStatus.textContent=TEXTS.camera_error;}}async function startPhotoPreview(){if(!photoCamera)return;try{const previewStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});photoCamera.srcObject=previewStream;photoCamera.style.display="block";if(photoPreview)photoPreview.style.display="none";}catch(error){personStatus.textContent=TEXTS.camera_error;}}async function sendLiveFrame(){if(!liveCamera||!cameraStream||liveCamera.videoWidth===0)return;const canvas=document.createElement("canvas");canvas.width=liveCamera.videoWidth;canvas.height=liveCamera.videoHeight;canvas.getContext("2d").drawImage(liveCamera,0,0,canvas.width,canvas.height);await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));}function setupPhotoCamera(){if(photoInput){photoInput.addEventListener("change",()=>{const file=photoInput.files&&photoInput.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{if(photoPreview){photoPreview.src=reader.result;photoPreview.style.display="block";}if(photoCamera)photoCamera.style.display="none";updateFaceStatus(reader.result);resultText.textContent="Picture loaded.";};reader.readAsDataURL(file);});}if(!SHOW_LIVE_CAMERA){startPhotoPreview();}}async function ensureRecordingStream(){if(recordingStream)return recordingStream;recordingStream=cameraStream||await navigator.mediaDevices.getUserMedia({video:true,audio:false});if(SHOW_LIVE_CAMERA&&liveCamera&&!liveCamera.srcObject){liveCamera.srcObject=recordingStream;}if(!SHOW_LIVE_CAMERA&&photoCamera&&!photoCamera.srcObject){photoCamera.srcObject=recordingStream;photoCamera.style.display="block";}return recordingStream;}function saveBlob(blob,name){const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1500);}function captureFromVideo(videoEl){if(!videoEl||videoEl.videoWidth===0)return null;const canvas=document.createElement("canvas");canvas.width=videoEl.videoWidth;canvas.height=videoEl.videoHeight;canvas.getContext("2d").drawImage(videoEl,0,0,canvas.width,canvas.height);return canvas;}async function takePictureAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(!canvas){resultText.textContent="Camera is not ready.";return;}canvas.toBlob(blob=>{if(blob)saveBlob(blob,"friday_picture.png");},"image/png");if(photoPreview){photoPreview.src=canvas.toDataURL("image/png");photoPreview.style.display="block";}await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Picture saved.";return;}if(photoInput){photoInput.click();resultText.textContent="Choose or capture a picture.";}else{resultText.textContent="Picture action unavailable.";}}async function startRecordingAction(){try{const stream=await ensureRecordingStream();recordingChunks=[];mediaRecorder=new MediaRecorder(stream);mediaRecorder.ondataavailable=(event)=>{if(event.data&&event.data.size>0)recordingChunks.push(event.data);};mediaRecorder.onstop=()=>{if(recordingChunks.length){saveBlob(new Blob(recordingChunks,{type:"video/webm"}),"friday_recording.webm");resultText.textContent="Recording saved.";}};mediaRecorder.start();resultText.textContent="Recording started.";}catch(error){resultText.textContent="Recording could not start.";}}function stopRecordingAction(){if(!mediaRecorder||mediaRecorder.state==="inactive"){resultText.textContent="No recording is running.";return;}mediaRecorder.stop();if(recordingStream&&!cameraStream){recordingStream.getTracks().forEach(track=>track.stop());recordingStream=null;}resultText.textContent="Stopping recording...";}async function startScanningAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(canvas){await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Scanning started.";return;}}if(photoInput){photoInput.click();resultText.textContent="Choose a picture to scan.";}else{resultText.textContent="Scanning unavailable.";}}function stopScanningAction(){personStatus.textContent=TEXTS.unknown;resultText.textContent="Scanning stopped.";}function mergeBuffers(chunks){let length=0;for(const chunk of chunks)length+=chunk.length;const result=new Float32Array(length);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}return result;}function encodeWav(samples,sampleRate){const buffer=new ArrayBuffer(44+samples.length*2);const view=new DataView(buffer);const writeString=(offset,str)=>{for(let i=0;i<str.length;i++)view.setUint8(offset+i,str.charCodeAt(i));};writeString(0,"RIFF");view.setUint32(4,36+samples.length*2,true);writeString(8,"WAVE");writeString(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);writeString(36,"data");view.setUint32(40,samples.length*2,true);let offset=44;for(let i=0;i<samples.length;i++,offset+=2){const s=Math.max(-1,Math.min(1,samples[i]));view.setInt16(offset,s<0?s*0x8000:s*0x7fff,true);}return new Blob([view],{type:"audio/wav"});}async function startBackendMic(){if(audioProcessor)return;try{audioStream=await navigator.mediaDevices.getUserMedia({audio:true});audioContext=new (window.AudioContext||window.webkitAudioContext)();audioSampleRate=audioContext.sampleRate;audioSource=audioContext.createMediaStreamSource(audioStream);audioProcessor=audioContext.createScriptProcessor(4096,1,1);audioChunks=[];audioProcessor.onaudioprocess=(event)=>{audioChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));};audioSource.connect(audioProcessor);audioProcessor.connect(audioContext.destination);voiceText.textContent=TEXTS.voice_live;setListeningUi(true);listenTimer=setTimeout(()=>stopBackendMic(false),listenCycleMs);}catch(error){alwaysListening=false;setListeningUi(false);voiceText.textContent=TEXTS.voice_error;}}async function stopBackendMic(manualStop){if(listenTimer){clearTimeout(listenTimer);listenTimer=null;}if(!audioProcessor||!audioContext){setListeningUi(false);voiceText.textContent=TEXTS.voice_error;return;}audioProcessor.disconnect();audioSource.disconnect();audioStream.getTracks().forEach(track=>track.stop());const contextToClose=audioContext;const samples=mergeBuffers(audioChunks);const wavBlob=encodeWav(samples,audioSampleRate);audioProcessor=null;audioSource=null;audioStream=null;audioContext=null;await contextToClose.close();try{const arrayBuffer=await wavBlob.arrayBuffer();const data=await postRaw("/transcribe-audio",arrayBuffer,"audio/wav");transcriptText=(data.text||"").trim().toLowerCase();voiceText.textContent=transcriptText||TEXTS.voice_empty;if(transcriptText){commandBox.value=transcriptText;await sendCommand();}}catch(error){voiceText.textContent=TEXTS.voice_error;}if(alwaysListening&&!manualStop){setTimeout(()=>startBackendMic(),250);}else{alwaysListening=false;setListeningUi(false);}}function setupVoice(){setListeningUi(false);micButton.onclick=async()=>{if(alwaysListening)return;alwaysListening=true;transcriptText="";await startBackendMic();};talkButton.onclick=async()=>{if(!alwaysListening&&!audioProcessor){resultText.textContent=TEXTS.use_mic_first;return;}alwaysListening=false;await stopBackendMic(true);};}async function sendPreset(command){commandBox.value=command;await sendCommand();}async function sendCommand(){const command=commandBox.value.trim().toLowerCase();if(!command){resultText.textContent=TEXTS.missing_command;return;}appendMessage("You",command);if(command==="take picture"){await takePictureAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start recording"){await startRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop recording"){stopRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start scanning"){await startScanningAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop scanning"){stopScanningAction();appendMessage("Assistant",resultText.textContent);try{await postJson("/command",{command});}catch(error){}return;}resultText.textContent=TEXTS.sending;try{const data=await postJson("/command",{command});const answer=data.message||"Done.";resultText.textContent=answer;appendMessage("Assistant",answer);speakAssistant(answer);}catch(error){resultText.textContent="Command failed.";}}async function toggleBan(userId){try{const data=await postJson("/admin/toggle-ban",{user_id:userId});resultText.textContent=data.message||TEXTS.updated;if(data.ok)location.reload();}catch(error){resultText.textContent="Action failed.";}}if(speakButton){speakButton.onclick=()=>speakAssistant(resultText.textContent);}if(downloadMp4Button&&mp4Url){downloadMp4Button.onclick=async()=>{const url=mp4Url.value.trim();if(!url){resultText.textContent="Enter an MP4 link first.";return;}commandBox.value=`download mp4 ${url}`;await sendCommand();};}if(activityButton){activityButton.onclick=openActivityLog;}if(activityClose){activityClose.onclick=()=>{activityWrap.style.display="none";activityWrap.innerHTML="";activityCloseWrap.style.display="none";activityError.textContent="";};}startLiveCamera();setupPhotoCamera();setupVoice();</script></body></html>"""
    page = page.replace(
        "__DOWNLOAD_PANEL__", f"{render_download_panel(lang)} {tutorial_panel}"
    )
    page = page.replace(
        "const TEXTS=__TEXTS__;",
        f"const TEXTS=__TEXTS__;const SHOW_TUTORIAL={json.dumps(show_tutorial)};",
    )
    page = page.replace(
        '<p class="sub">__VOICE_SUB__</p><div class="actions">',
        '<p class="sub">__VOICE_SUB__</p><div id="mobileMediaNotice" class="notice" style="display:none"></div><div class="actions">',
    )
    page = page.replace(
        '__CAMERA_SECTION__<section class="panel"><h2>__VOICE_TITLE__</h2>',
        '__CAMERA_SECTION__<section class="panel"><h2>Phone Viewing</h2><p class="sub">Share this phone screen after permission is granted.</p><div class="camera-box"><video id="phoneView'
        ' autoplay playsinline muted style="display:none"></video><div id="phoneViewStatus" class="status">Phone viewing is off.</div></div></section><section class="panel"><h2>__VOICE_TITLE__</h2>',
    )
    page = page.replace(
        "const TEXTS=__TEXTS__;const SHOW_TUTORIAL=",
        f"const TEXTS=__TEXTS__;const PUBLIC_URL={json.dumps(public_url)};const SHOW_TUTORIAL=",
    )
    page = page.replace(
        'const activityMeta=document.getElementById("activityMeta");',
        'const activityMeta=document.getElementById("activityMeta");const tutorialButton=document.getElementById("tutorialButton");const tutorialWrap=document.getElementById("tutorialWrap");const tutorialClose=document.getElementById("tutorialClose");const mobileMediaNotice=document.getElementById("mobileMediaNotice");const IS_SECURE_ORIGIN=window.isSecureContext||location.protocol==="https:"||location.hostname==="localhost"||location.hostname==="127.0.0.1";let audioMonitorGain=null;let liveFrameTimer=null;let torchStream=null;let torchTrack=null;let torchEnabled=false;',
    )
    page = page.replace(
        "function speakAssistant(text){",
        'function toggleTutorial(open){if(!tutorialWrap)return;tutorialWrap.style.display=open?"block":"none";if(tutorialClose)tutorialClose.style.display=open?"inline-flex":"none";}function showMobileMediaNotice(message){if(!mobileMediaNotice)return;mobileMediaNotice.textContent=message||"";mobileMediaNotice.style.display=message?"block":"none";}function getSecureMediaMessage(kind){const label=kind==="audio"?"microphone":"camera";if(PUBLIC_URL&&PUBLIC_URL.startsWith("https://"))return `Mobile ${label} needs a secure link. Open the Public link for ${label} access.`;return `Mobile ${label} needs HTTPS. Open this app from a secure public link, not the family Wi-Fi HTTP link.`;}function requireSecureMedia(kind){if(IS_SECURE_ORIGIN)return true;const message=getSecureMediaMessage(kind);showMobileMediaNotice(message);if(kind==="audio"&&voiceText)voiceText.textContent=message;if(kind==="video"&&personStatus)personStatus.textContent=message;if(resultText)resultText.textContent=message;return false;}function getVideoConstraints(preferRear){return {video:{facingMode:{ideal:preferRear?"environment":"user"},width:{ideal:1280},height:{ideal:720}},audio:false};}function getAudioConstraints(){return {audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1}};}async function attachVideoStream(videoEl,stream){if(!videoEl)return;videoEl.srcObject=stream;videoEl.setAttribute("playsinline","");videoEl.muted=true;try{await videoEl.play();}catch(error){}}function getRecordingMimeType(){if(!window.MediaRecorder||!MediaRecorder.isTypeSupported)return "";for(const type of["video/webm;codecs=vp9,opus","video/webm;codecs=vp8,opus","video/webm","video/mp4"]){if(MediaRecorder.isTypeSupported(type))return type;}return "";}function getRecordingExtension(mimeType){return mimeType&&mimeType.includes("mp4")?"mp4":"webm";}async function enableLightsAction(){if(!requireSecureMedia("video"))return false;try{if(!torchStream){torchStream=await navigator.mediaDevices.getUserMedia(getVideoConstraints(true));}torchTrack=torchStream.getVideoTracks()[0];const capabilities=torchTrack&&torchTrack.getCapabilities?torchTrack.getCapabilities():{};if(!capabilities.torch){resultText.textContent="This phone/browser does not support flashlight control.";return false;}await torchTrack.applyConstraints({advanced:[{torch:true}]});torchEnabled=true;resultText.textContent="Phone light enabled on this device.";return true;}catch(error){resultText.textContent="Phone light could not be enabled on this device.";return false;}}async function disableLightsAction(){try{if(torchTrack){const capabilities=torchTrack.getCapabilities?torchTrack.getCapabilities():{};if(capabilities.torch){await torchTrack.applyConstraints({advanced:[{torch:false}]});}}if(torchStream){torchStream.getTracks().forEach(track=>track.stop());}torchStream=null;torchTrack=null;torchEnabled=false;resultText.textContent="Phone light disabled on this device.";return true;}catch(error){resultText.textContent="Phone light could not be disabled on this device.";return false;}}function speakAssistant(text){',
    )
    page = page.replace(
        "async function startLiveCamera(){if(!SHOW_LIVE_CAMERA||!liveCamera)return;try{cameraStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});liveCamera.srcObject=cameraStream;setInterval(sendLiveFrame,3000);}catch(error){personStatus.textContent=TEXTS.camera_error;}}",
        'async function startLiveCamera(){if(!SHOW_LIVE_CAMERA||!liveCamera||!requireSecureMedia("video"))return;try{cameraStream=await navigator.mediaDevices.getUserMedia(getVideoConstraints(false));await attachVideoStream(liveCamera,cameraStream);if(liveFrameTimer)clearInterval(liveFrameTimer);liveFrameTimer=setInterval(sendLiveFrame,3000);showMobileMediaNotice("");}catch(error){personStatus.textContent=TEXTS.camera_error;}}',
    )
    page = page.replace(
        'async function startPhotoPreview(){if(!photoCamera)return;try{const previewStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});photoCamera.srcObject=previewStream;photoCamera.style.display="block";if(photoPreview)photoPreview.style.display="none";}catch(error){personStatus.textContent=TEXTS.camera_error;}}',
        'async function startPhotoPreview(){if(!photoCamera||!requireSecureMedia("video"))return;try{const previewStream=await navigator.mediaDevices.getUserMedia(getVideoConstraints(true));await attachVideoStream(photoCamera,previewStream);photoCamera.style.display="block";if(photoPreview)photoPreview.style.display="none";showMobileMediaNotice("");}catch(error){personStatus.textContent=TEXTS.camera_error;}}',
    )
    page = page.replace(
        'function setupPhotoCamera(){if(photoInput){photoInput.addEventListener("change",()=>{const file=photoInput.files&&photoInput.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{if(photoPreview){photoPreview.src=reader.result;photoPreview.style.display="block";}if(photoCamera)photoCamera.style.display="none";updateFaceStatus(reader.result);resultText.textContent="Picture loaded.";};reader.readAsDataURL(file);});}if(!SHOW_LIVE_CAMERA){startPhotoPreview();}}',
        'function setupPhotoCamera(){if(photoInput){photoInput.addEventListener("change",()=>{const file=photoInput.files&&photoInput.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{if(photoPreview){photoPreview.src=reader.result;photoPreview.style.display="block";}if(photoCamera)photoCamera.style.display="none";updateFaceStatus(reader.result);resultText.textContent="Picture loaded.";};reader.readAsDataURL(file);});}}',
    )
    page = page.replace(
        'async function ensureRecordingStream(){if(recordingStream)return recordingStream;recordingStream=cameraStream||await navigator.mediaDevices.getUserMedia({video:true,audio:false});if(SHOW_LIVE_CAMERA&&liveCamera&&!liveCamera.srcObject){liveCamera.srcObject=recordingStream;}if(!SHOW_LIVE_CAMERA&&photoCamera&&!photoCamera.srcObject){photoCamera.srcObject=recordingStream;photoCamera.style.display="block";}return recordingStream;}',
        'async function ensureRecordingStream(){if(recordingStream)return recordingStream;if(!requireSecureMedia("video"))throw new Error("insecure");recordingStream=cameraStream||await navigator.mediaDevices.getUserMedia(getVideoConstraints(!SHOW_LIVE_CAMERA));if(SHOW_LIVE_CAMERA&&liveCamera&&!liveCamera.srcObject){await attachVideoStream(liveCamera,recordingStream);}if(!SHOW_LIVE_CAMERA&&photoCamera&&!photoCamera.srcObject){await attachVideoStream(photoCamera,recordingStream);photoCamera.style.display="block";}return recordingStream;}',
    )
    page = page.replace(
        'async function takePictureAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(!canvas){resultText.textContent="Camera is not ready.";return;}canvas.toBlob(blob=>{if(blob)saveBlob(blob,"friday_picture.png");},"image/png");if(photoPreview){photoPreview.src=canvas.toDataURL("image/png");photoPreview.style.display="block";}await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Picture saved.";return;}if(photoInput){photoInput.click();resultText.textContent="Choose or capture a picture.";}else{resultText.textContent="Picture action unavailable.";}}',
        'async function takePictureAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject&&IS_SECURE_ORIGIN){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(!canvas){resultText.textContent="Camera is not ready.";return;}canvas.toBlob(blob=>{if(blob)saveBlob(blob,"friday_picture.png");},"image/png");if(photoPreview){photoPreview.src=canvas.toDataURL("image/png");photoPreview.style.display="block";}await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Picture saved.";return;}if(photoInput){photoInput.click();resultText.textContent=IS_SECURE_ORIGIN?"Choose or capture a picture.":"Camera preview is blocked on this phone link. Use file capture or open the secure public link.";}else{resultText.textContent="Picture action unavailable.";}}',
    )
    page = page.replace(
        'async function startRecordingAction(){try{const stream=await ensureRecordingStream();recordingChunks=[];mediaRecorder=new MediaRecorder(stream);mediaRecorder.ondataavailable=(event)=>{if(event.data&&event.data.size>0)recordingChunks.push(event.data);};mediaRecorder.onstop=()=>{if(recordingChunks.length){saveBlob(new Blob(recordingChunks,{type:"video/webm"}),"friday_recording.webm");resultText.textContent="Recording saved.";}};mediaRecorder.start();resultText.textContent="Recording started.";}catch(error){resultText.textContent="Recording could not start.";}}',
        'async function startRecordingAction(){if(!window.MediaRecorder){resultText.textContent="This browser does not support video recording.";return;}try{const stream=await ensureRecordingStream();const mimeType=getRecordingMimeType();recordingChunks=[];mediaRecorder=mimeType?new MediaRecorder(stream,{mimeType}):new MediaRecorder(stream);mediaRecorder.ondataavailable=(event)=>{if(event.data&&event.data.size>0)recordingChunks.push(event.data);};mediaRecorder.onstop=()=>{if(recordingChunks.length){const finalType=mediaRecorder.mimeType||mimeType||"video/webm";const extension=getRecordingExtension(finalType);saveBlob(new Blob(recordingChunks,{type:finalType}),`friday_recording.${extension}`);resultText.textContent="Recording saved.";}};mediaRecorder.start();resultText.textContent="Recording started.";}catch(error){resultText.textContent=error&&error.message==="insecure"?getSecureMediaMessage("video"):"Recording could not start.";}}',
    )
    page = page.replace(
        'async function startScanningAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(canvas){await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Scanning started.";return;}}if(photoInput){photoInput.click();resultText.textContent="Choose a picture to scan.";}else{resultText.textContent="Scanning unavailable.";}}',
        'async function startScanningAction(){const sourceVideo=SHOW_LIVE_CAMERA?liveCamera:photoCamera;if(!SHOW_LIVE_CAMERA&&!sourceVideo?.srcObject&&IS_SECURE_ORIGIN){await startPhotoPreview();}if(sourceVideo&&sourceVideo.videoWidth>0){const canvas=captureFromVideo(sourceVideo);if(canvas){await updateFaceStatus(canvas.toDataURL("image/jpeg",0.75));resultText.textContent="Scanning started.";return;}}if(photoInput){photoInput.click();resultText.textContent=IS_SECURE_ORIGIN?"Choose a picture to scan.":"Live camera scan is blocked on this phone link. Use file capture or open the secure public link.";}else{resultText.textContent="Scanning unavailable.";}}',
    )
    page = page.replace(
        "async function startBackendMic(){if(audioProcessor)return;try{audioStream=await navigator.mediaDevices.getUserMedia({audio:true});audioContext=new (window.AudioContext||window.webkitAudioContext)();audioSampleRate=audioContext.sampleRate;audioSource=audioContext.createMediaStreamSource(audioStream);audioProcessor=audioContext.createScriptProcessor(4096,1,1);audioChunks=[];audioProcessor.onaudioprocess=(event)=>{audioChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));};audioSource.connect(audioProcessor);audioProcessor.connect(audioContext.destination);voiceText.textContent=TEXTS.voice_live;setListeningUi(true);listenTimer=setTimeout(()=>stopBackendMic(false),listenCycleMs);}catch(error){alwaysListening=false;setListeningUi(false);voiceText.textContent=TEXTS.voice_error;}}",
        'async function startBackendMic(){if(audioProcessor)return;if(!requireSecureMedia("audio"))return;try{audioStream=await navigator.mediaDevices.getUserMedia(getAudioConstraints());audioContext=new (window.AudioContext||window.webkitAudioContext)();if(audioContext.state==="suspended")await audioContext.resume();audioSampleRate=audioContext.sampleRate;audioSource=audioContext.createMediaStreamSource(audioStream);audioProcessor=audioContext.createScriptProcessor(4096,1,1);audioMonitorGain=audioContext.createGain();audioMonitorGain.gain.value=0;audioChunks=[];audioProcessor.onaudioprocess=(event)=>{audioChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));};audioSource.connect(audioProcessor);audioProcessor.connect(audioMonitorGain);audioMonitorGain.connect(audioContext.destination);voiceText.textContent=TEXTS.voice_live;setListeningUi(true);showMobileMediaNotice("");listenTimer=setTimeout(()=>stopBackendMic(false),listenCycleMs);}catch(error){alwaysListening=false;setListeningUi(false);voiceText.textContent=TEXTS.voice_error;}}',
    )
    page = page.replace(
        'async function stopBackendMic(manualStop){if(listenTimer){clearTimeout(listenTimer);listenTimer=null;}if(!audioProcessor||!audioContext){setListeningUi(false);voiceText.textContent=TEXTS.voice_error;return;}audioProcessor.disconnect();audioSource.disconnect();audioStream.getTracks().forEach(track=>track.stop());const contextToClose=audioContext;const samples=mergeBuffers(audioChunks);const wavBlob=encodeWav(samples,audioSampleRate);audioProcessor=null;audioSource=null;audioStream=null;audioContext=null;await contextToClose.close();try{const arrayBuffer=await wavBlob.arrayBuffer();const data=await postRaw("/transcribe-audio",arrayBuffer,"audio/wav");transcriptText=(data.text||"").trim().toLowerCase();voiceText.textContent=transcriptText||TEXTS.voice_empty;if(transcriptText){commandBox.value=transcriptText;await sendCommand();}}catch(error){voiceText.textContent=TEXTS.voice_error;}if(alwaysListening&&!manualStop){setTimeout(()=>startBackendMic(),250);}else{alwaysListening=false;setListeningUi(false);}}',
        'async function stopBackendMic(manualStop){if(listenTimer){clearTimeout(listenTimer);listenTimer=null;}if(!audioProcessor||!audioContext){setListeningUi(false);voiceText.textContent=TEXTS.voice_error;return;}audioProcessor.disconnect();audioSource.disconnect();if(audioMonitorGain){audioMonitorGain.disconnect();audioMonitorGain=null;}audioStream.getTracks().forEach(track=>track.stop());const contextToClose=audioContext;const samples=mergeBuffers(audioChunks);const wavBlob=encodeWav(samples,audioSampleRate);audioProcessor=null;audioSource=null;audioStream=null;audioContext=null;await contextToClose.close();try{const arrayBuffer=await wavBlob.arrayBuffer();const data=await postRaw("/transcribe-audio",arrayBuffer,"audio/wav");transcriptText=(data.text||"").trim().toLowerCase();voiceText.textContent=transcriptText||TEXTS.voice_empty;if(transcriptText){commandBox.value=transcriptText;await sendCommand();}}catch(error){voiceText.textContent=TEXTS.voice_error;}if(alwaysListening&&!manualStop){setTimeout(()=>startBackendMic(),250);}else{alwaysListening=false;setListeningUi(false);}}',
    )
    page = page.replace(
        'if(activityClose){activityClose.onclick=()=>{activityWrap.style.display="none";activityWrap.innerHTML="";activityCloseWrap.style.display="none";activityError.textContent="";};}startLiveCamera();setupPhotoCamera();setupVoice();',
        'if(activityClose){activityClose.onclick=()=>{activityWrap.style.display="none";activityWrap.innerHTML="";activityCloseWrap.style.display="none";activityError.textContent="";};}if(tutorialButton){tutorialButton.onclick=()=>toggleTutorial(true);}if(tutorialClose){tutorialClose.onclick=()=>toggleTutorial(false);}if(SHOW_TUTORIAL){toggleTutorial(true);}if(!IS_SECURE_ORIGIN&&/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)){showMobileMediaNotice(getSecureMediaMessage("video"));}startLiveCamera();setupPhotoCamera();setupVoice();',
    )
    page = page.replace(
        'async function sendCommand(){const command=commandBox.value.trim().toLowerCase();if(!command){resultText.textContent=TEXTS.missing_command;return;}appendMessage("You",command);if(command==="take picture"){await takePictureAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start recording"){await startRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop recording"){stopRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start scanning"){await startScanningAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop scanning"){stopScanningAction();appendMessage("Assistant",resultText.textContent);try{await postJson("/command",{command});}catch(error){}return;}resultText.textContent=TEXTS.sending;try{const data=await postJson("/command",{command});const answer=data.message||"Done.";resultText.textContent=answer;appendMessage("Assistant",answer);speakAssistant(answer);}catch(error){resultText.textContent="Command failed.";}}',
        'async function sendCommand(){const command=commandBox.value.trim().toLowerCase();if(!command){resultText.textContent=TEXTS.missing_command;return;}appendMessage("You",command);if(command==="take picture"){await takePictureAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start recording"){await startRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop recording"){stopRecordingAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="start scanning"){await startScanningAction();appendMessage("Assistant",resultText.textContent);return;}if(command==="stop scanning"){stopScanningAction();appendMessage("Assistant",resultText.textContent);try{await postJson("/command",{command});}catch(error){}return;}if(["lights on","light on","enable lights","enable light","enable ligths","ligths on","turn on lights","turn on ligths"].includes(command)){await enableLightsAction();appendMessage("Assistant",resultText.textContent);return;}if(["lights off","light off","disable lights","disable light","disable ligths","ligths off","turn off lights","turn off ligths"].includes(command)){await disableLightsAction();appendMessage("Assistant",resultText.textContent);return;}resultText.textContent=TEXTS.sending;try{const data=await postJson("/command",{command});const answer=data.message||"Done.";resultText.textContent=answer;appendMessage("Assistant",answer);speakAssistant(answer);}catch(error){resultText.textContent="Command failed.";}}',
    )

    replacements = {
        "__TITLE__": html.escape(user["assistant_name"]),
        "__CSS__": css,
        "__ASSISTANT__": html.escape(user["assistant_name"]),
        "__SUBTITLE__": html.escape(t(lang, "subtitle")),
        "__NAME__": html.escape(user["display_name"]),
        "__TAG__": html.escape(theme["tag"]),
        "__LOGOUT__": html.escape(t(lang, "logout")),
        "__CAMERA_SECTION__": camera_section,
        "__VOICE_TITLE__": html.escape(t(lang, "voice_title")),
        "__VOICE_SUB__": html.escape(t(lang, "voice_sub")),
        "__MIC__": html.escape(t(lang, "mic")),
        "__TALK__": html.escape(t(lang, "talk")),
        "__QUICK_BUTTONS__": "".join(quick_buttons),
        "__VOICE_DEFAULT__": html.escape(t(lang, "voice_default")),
        "__PLACEHOLDER__": html.escape(t(lang, "placeholder")),
        "__WAITING__": html.escape(t(lang, "waiting")),
        "__SEND__": html.escape(t(lang, "send")),
        "__ACTIVITY_PANEL__": render_activity_panel(user_id, lang),
        "__COMMANDS__": html.escape(t(lang, "commands")),
        "__COMMANDS_SUB__": html.escape(t(lang, "commands_sub")),
        "__COMMAND_CARDS__": command_cards_for(user_id),
        "__LINKS__": html.escape(t(lang, "links")),
        "__LINK_BLOCKS__": "".join(link_blocks),
        "__DOWNLOAD_PANEL__": render_download_panel(lang),
        "__WAKE_WORD__": html.escape(memory.get("wake_word", "")),
        "__FAVORITE_GAME__": html.escape(
            memory.get("memory", {}).get("favorite game", "")
        ),
        "__ABILITIES__": render_abilities_panel(user_id, lang),
        "__MESSAGES__": render_messages_panel(user_id, lang),
        "__ADMIN__": admin_panel,
        "__LANG__": json.dumps(lang),
        "__SHOW_CAMERA__": json.dumps(show_live_camera),
        "__TEXTS__": json.dumps(TEXT[lang]),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page.encode("utf-8")


def decode_data_url(image_data):
    if "," not in image_data:
        return None
    try:
        _, encoded = image_data.split(",", 1)
        raw = base64.b64decode(encoded)
        return cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def set_last_person_for_everyone(result):
    with STATE_LOCK:
        for user_id in MEMORY:
            MEMORY[user_id]["last_person"] = result
        save_memory()


def detect_person(frame):
    if frame is None:
        result = {"status": "unknown", "name": ""}
        set_last_person_for_everyone(result)
        return result
    if face_recognition is not None and KNOWN_FACE_ENCODINGS:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, locations)
        for encoding in encodings:
            matches = face_recognition.compare_faces(
                KNOWN_FACE_ENCODINGS, encoding, tolerance=0.45
            )
            if True in matches:
                result = {
                    "status": "known",
                    "name": KNOWN_FACE_NAMES[matches.index(True)],
                }
                set_last_person_for_everyone(result)
                return result
        if locations:
            result = {"status": "unknown", "name": ""}
            set_last_person_for_everyone(result)
            return result
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    classifier = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    classifier.detectMultiScale(gray, 1.1, 5)
    result = {"status": "unknown", "name": ""}
    set_last_person_for_everyone(result)
    return result


def open_target(target):
    try:
        os.startfile(target)
        return True
    except Exception:
        try:
            webbrowser.open(target)
            return True
        except Exception:
            return False


def launch_app(alias):
    for item in APP_ALIASES.get(alias, [alias]):
        if open_target(item):
            return True
    return False


def take_screenshot():
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_path = CAPTURE_DIR / f"screenshot_{timestamp}.png"
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$bounds=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp=New-Object System.Drawing.Bitmap $bounds.Width,$bounds.Height; "
        "$graphics=[System.Drawing.Graphics]::FromImage($bmp); "
        "$graphics.CopyFromScreen($bounds.Location,[System.Drawing.Point]::Empty,$bounds.Size); "
        f"$bmp.Save('{str(file_path).replace(chr(92), chr(47))}',[System.Drawing.Imaging.ImageFormat]::Png); "
        "$graphics.Dispose(); $bmp.Dispose()"
    )
    try:
        subprocess.run(
            ["powershell", "-STA", "-Command", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return file_path.name if file_path.exists() else None
    except Exception:
        return None


def close_named_app(app_name):
    app = app_name.strip().lower().replace(".exe", "")
    if not app:
        return False
    subprocess.run(
        ["taskkill", "/IM", f"{app}.exe", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def close_other_apps():
    import csv
    from io import StringIO

    current_pid = str(os.getpid())
    try:
        output = subprocess.check_output(
            ["tasklist", "/fo", "csv", "/nh"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return 0
    closed = 0
    for row in csv.reader(StringIO(output)):
        if len(row) < 2:
            continue
        image_name = row[0].strip('"')
        pid = row[1].strip('"')
        if image_name in SAFE_PROCESSES or pid == current_pid:
            continue
        subprocess.run(
            ["taskkill", "/PID", pid, "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        closed += 1
    return closed


def add_notification(user_id, text):
    with STATE_LOCK:
        bucket = MEMORY[user_id]["notifications"]
        bucket.append({"time": time.strftime("%H:%M:%S"), "text": text})
        del bucket[:-12]
        save_memory()


def add_message(user_id, role, text):
    with STATE_LOCK:
        bucket = MEMORY[user_id]["messages"]
        bucket.append({"time": time.strftime("%H:%M:%S"), "role": role, "text": text})
        del bucket[:-20]
        save_memory()


def add_activity(user_id, text):
    if user_id not in {"arzu", "zehra"}:
        return
    with STATE_LOCK:
        bucket = MEMORY[user_id]["activity_log"]
        bucket.append({"time": time.strftime("%H:%M:%S"), "text": text})
        del bucket[:-20]
        save_memory()


def get_owner_activity_html():
    items = []
    merged = []
    for target_id in ("arzu", "zehra"):
        for item in MEMORY[target_id].get("activity_log", [])[-12:]:
            merged.append(
                {
                    "time": item.get("time", ""),
                    "text": f'{USERS[target_id]["display_name"]}: {item.get("text", "")}',
                }
            )
    for item in merged[-16:][::-1]:
        stamp = html.escape(item.get("time", ""))
        text = html.escape(item.get("text", ""))
        items.append(
            f'<div class="message-item"><div class="small">{stamp}</div><div>{text}</div></div>'
        )
    if not items:
        items.append(
            '<div class="message-item"><div class="small">No activity yet.</div></div>'
        )
    return "".join(items)


def download_mp4_file(url):
    if not url.lower().startswith(("http://", "https://")):
        return None, "invalid"
    if ".mp4" not in url.lower():
        return None, "not_mp4"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_path = DOWNLOAD_DIR / f"download_{timestamp}.mp4"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            if "video/mp4" not in content_type.lower() and not url.lower().endswith(
                ".mp4"
            ):
                return None, "not_mp4"
            file_path.write_bytes(response.read())
        return file_path.name, "ok"
    except Exception:
        return None, "failed"


def transcribe_wav_bytes(audio_bytes, language):
    if sr is None:
        return None, "SpeechRecognition not installed."
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        lang_code = "az-AZ" if language == "az" else "en-US"
        text = recognizer.recognize_google(audio, language=lang_code)
        return text, None
    except Exception:
        return None, "Could not understand audio."


def run_timer(user_id, seconds):
    def worker():
        time.sleep(seconds)
        add_notification(user_id, f"Timer finished after {seconds} seconds.")

    threading.Thread(target=worker, daemon=True).start()


def run_reminder(user_id, lang, message, seconds):
    def worker():
        time.sleep(seconds)
        add_notification(
            user_id,
            localized(lang, f"Reminder: {message}.", f"Xatirlatma: {message}."),
        )

    threading.Thread(target=worker, daemon=True).start()


def family_public_link():
    public_url = get_public_url()
    return public_url or LOCAL_URL


def get_weather_location(user_id):
    memory = MEMORY.get(user_id, {})
    stored = memory.get("memory", {}).get("weather location", "").strip()
    if stored:
        return stored
    return os.getenv("FRIDAY_WEATHER_LOCATION", "Baku")


def fetch_json(url, timeout=8):
    request = urllib.request.Request(url, headers={"User-Agent": "FridayAI/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def air_quality_label(us_aqi, lang):
    if us_aqi is None:
        return localized(lang, "Unknown", "Namelum")
    if us_aqi <= 50:
        return localized(lang, "Good", "Yaxsi")
    if us_aqi <= 100:
        return localized(lang, "Moderate", "Orta")
    if us_aqi <= 150:
        return localized(
            lang, "Unhealthy for sensitive groups", "Hessas insanlar ucun ziyanli"
        )
    if us_aqi <= 200:
        return localized(lang, "Unhealthy", "Ziyanli")
    if us_aqi <= 300:
        return localized(lang, "Very unhealthy", "Cox ziyanli")
    return localized(lang, "Hazardous", "Tehlukeli")


def school_work_advice(lang, weather):
    advice = []
    if weather["is_snowing"]:
        advice.append(localized(lang, "Wear boots for the trip.", "Yolda cekme geyin."))
    if weather["is_raining"]:
        advice.append(localized(lang, "Take an umbrella.", "Ceter gotur."))
    if weather["wind_kph"] >= 35:
        advice.append(
            localized(
                lang,
                "A jacket will help because it is windy.",
                "Kulek gucludur, kurtka geyin.",
            )
        )
    if weather.get("uv_index", 0) >= 6:
        advice.append(
            localized(
                lang, "Carry sunscreen or a cap.", "Gunes kremi ve ya papaq gotur."
            )
        )
    if weather["temp_c"] <= 5:
        advice.append(
            localized(
                lang,
                "Keep warm on the way to school or work.",
                "Mektebe ve ya ise gedende isti geyin.",
            )
        )
    if weather["temp_c"] >= 30:
        advice.append(localized(lang, "Bring extra water.", "Elave su gotur."))
    if (
        weather.get("air_quality_us_aqi") is not None
        and weather["air_quality_us_aqi"] > 100
    ):
        advice.append(
            localized(
                lang,
                "If possible, limit long time outside.",
                "Mumkundurse, cox vaxt colde qalma.",
            )
        )
    if not advice:
        advice.append(
            localized(
                lang,
                "No extra school or work gear needed today.",
                "Bu gun elave mekteb ve ya is esyasi lazim deyil.",
            )
        )
    return " ".join(advice)


def get_weather_or_error(user_id, lang):
    location = get_weather_location(user_id)
    try:
        return fetch_weather_summary(location), None
    except Exception:
        return None, localized(
            lang,
            "Weather could not be loaded right now.",
            "Hava melumati indi yuklenmedi.",
        )


def weather_brief(lang, weather):
    return localized(
        lang,
        (
            f"Weather in {weather['location']}: {weather['description']}, "
            f"{weather['temp_c']}C now, feels like {weather['feels_like_c']}C, "
            f"high {weather['max_temp_c']}C, low {weather['min_temp_c']}C."
        ),
        (
            f"{weather['location']} ucun hava: {weather['description']}, "
            f"indi {weather['temp_c']}C, hiss olunan {weather['feels_like_c']}C, "
            f"en yuksek {weather['max_temp_c']}C, en asagi {weather['min_temp_c']}C."
        ),
    )


def weekly_forecast_text(lang, weather):
    summary = "; ".join(
        f"{item['day']}: {item['high_c']}C/{item['low_c']}C, {item['description']}"
        for item in weather.get("weekly_forecast", [])
    )
    return localized(
        lang, f"Weekly forecast: {summary}", f"Heftelik proqnoz: {summary}"
    )


def precipitation_text(lang, weather):
    if weather["is_snowing"]:
        return localized(
            lang,
            f"Snow is possible today ({weather['chance_of_snow']}% chance).",
            f"Bu gun qar ehtimali var ({weather['chance_of_snow']}% ehtimal).",
        )
    if weather["is_raining"]:
        return localized(
            lang,
            f"Rain is possible today ({weather['chance_of_rain']}% chance).",
            f"Bu gun yagis ehtimali var ({weather['chance_of_rain']}% ehtimal).",
        )
    return localized(lang, "No rain or snow expected.", "Yagis ve ya qar gozlenilmir.")


def fetch_weather_summary(location):
    safe_location = (location or "Baku").strip().replace(" ", "+")
    url = f"https://wttr.in/{safe_location}?format=j1"
    payload = fetch_json(url)

    current = (payload.get("current_condition") or [{}])[0]
    today = (payload.get("weather") or [{}])[0]
    weekly = payload.get("weather") or []
    hourly = today.get("hourly") or []
    astronomy = (today.get("astronomy") or [{}])[0]
    nearest_area = (payload.get("nearest_area") or [{}])[0]
    descriptions = " ".join(
        " ".join(item.get("value", "") for item in hour.get("weatherDesc", []))
        for hour in hourly
    ).lower()
    current_desc = " ".join(
        item.get("value", "") for item in current.get("weatherDesc", [])
    ).strip()

    chance_of_rain = max(
        (int(hour.get("chanceofrain", "0") or 0) for hour in hourly), default=0
    )
    chance_of_snow = max(
        (int(hour.get("chanceofsnow", "0") or 0) for hour in hourly), default=0
    )
    precip_mm = float(current.get("precipMM", "0") or 0)
    temp_c = int(float(current.get("temp_C", "0") or 0))
    feels_like_c = int(
        float(current.get("FeelsLikeC", current.get("temp_C", "0")) or 0)
    )
    max_temp_c = int(float(today.get("maxtempC", current.get("temp_C", "0")) or 0))
    min_temp_c = int(float(today.get("mintempC", current.get("temp_C", "0")) or 0))
    wind_kph = int(float(current.get("windspeedKmph", "0") or 0))
    humidity = int(float(current.get("humidity", "0") or 0))
    uv_index = int(float(current.get("uvIndex", "0") or 0))
    latitude = nearest_area.get("latitude")
    longitude = nearest_area.get("longitude")

    desc_blob = f"{current_desc} {descriptions}".lower()
    is_snowing = (
        chance_of_snow >= 35
        or "snow" in desc_blob
        or "sleet" in desc_blob
        or "blizzard" in desc_blob
    )
    is_raining = not is_snowing and (
        chance_of_rain >= 35
        or precip_mm > 0
        or "rain" in desc_blob
        or "drizzle" in desc_blob
        or "shower" in desc_blob
    )

    weekly_forecast = []
    for day in weekly[:5]:
        date_raw = day.get("date", "")
        try:
            day_name = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%a")
        except Exception:
            day_name = date_raw
        day_desc = ""
        for hour in day.get("hourly") or []:
            values = [
                item.get("value", "")
                for item in hour.get("weatherDesc", [])
                if item.get("value")
            ]
            if values:
                day_desc = values[0]
                break
        weekly_forecast.append(
            {
                "day": day_name,
                "high_c": int(float(day.get("maxtempC", "0") or 0)),
                "low_c": int(float(day.get("mintempC", "0") or 0)),
                "description": day_desc or "Unknown",
            }
        )

    air_quality_us_aqi = None
    if latitude and longitude:
        try:
            aq_url = (
                "https://air-quality-api.open-meteo.com/v1/air-quality"
                f"?latitude={latitude}&longitude={longitude}&current=us_aqi"
            )
            aq_payload = fetch_json(aq_url)
            air_quality_us_aqi = aq_payload.get("current", {}).get("us_aqi")
            if air_quality_us_aqi is not None:
                air_quality_us_aqi = int(float(air_quality_us_aqi))
        except Exception:
            air_quality_us_aqi = None

    return {
        "location": location,
        "temp_c": temp_c,
        "feels_like_c": feels_like_c,
        "max_temp_c": max_temp_c,
        "min_temp_c": min_temp_c,
        "wind_kph": wind_kph,
        "humidity": humidity,
        "description": current_desc or "Unknown",
        "chance_of_rain": chance_of_rain,
        "chance_of_snow": chance_of_snow,
        "is_raining": is_raining,
        "is_snowing": is_snowing,
        "sunrise": astronomy.get("sunrise", "--"),
        "sunset": astronomy.get("sunset", "--"),
        "uv_index": uv_index,
        "air_quality_us_aqi": air_quality_us_aqi,
        "weekly_forecast": weekly_forecast,
    }


def outfit_advice(lang, weather):
    temp_c = weather["temp_c"]
    if weather["is_snowing"]:
        return localized(
            lang,
            "Wear a warm coat, boots, and gloves.",
            "Qalin kurtka, cekme ve elcek geyin.",
        )
    if weather["is_raining"]:
        if temp_c <= 10:
            return localized(
                lang,
                "Wear a jacket and take an umbrella.",
                "Kurtka geyin ve ceter gotur.",
            )
        return localized(
            lang,
            "Wear light layers and take an umbrella.",
            "Nazik qatlar geyin ve ceter gotur.",
        )
    if temp_c <= 5:
        return localized(
            lang,
            "Wear a heavy coat. It is very cold.",
            "Qalin paltar geyin. Cox soyuqdur.",
        )
    if temp_c <= 12:
        return localized(lang, "Wear a jacket or hoodie.", "Kurtka ve ya huddi geyin.")
    if temp_c <= 20:
        return localized(
            lang, "A light jacket should be enough.", "Nazik kurtka kifayet eder."
        )
    if temp_c <= 28:
        return localized(
            lang,
            "A t-shirt or light clothes should feel good.",
            "Futbolka ve ya yungu geyim yaxsi olar.",
        )
    return localized(
        lang,
        "Wear very light clothes and drink extra water.",
        "Cox yungu geyim geyin ve daha cox su ic.",
    )


def morning_mode_report(user_id, lang):
    now = time.localtime()
    current_time = time.strftime("%H:%M", now)
    day_name = time.strftime("%A", now)
    date_text = time.strftime("%d %B %Y", now)
    weather, error = get_weather_or_error(user_id, lang)
    if error:
        return localized(
            lang,
            f"Morning mode is ready. Today is {day_name}, {date_text}. Time: {current_time}. Weather could not be loaded right now.",
            f"Seher rejimi hazirdir. Bugun {day_name}, {date_text}. Vaxt: {current_time}. Hava melumati indi yuklenmedi.",
        )
    precipitation_line = precipitation_text(lang, weather)
    weekly_text = "; ".join(
        f"{item['day']}: {item['high_c']}C/{item['low_c']}C, {item['description']}"
        for item in weather.get("weekly_forecast", [])
    )
    air_quality_text = localized(
        lang,
        f"Air quality: {air_quality_label(weather.get('air_quality_us_aqi'), lang)}"
        + (
            f" (US AQI {weather['air_quality_us_aqi']})."
            if weather.get("air_quality_us_aqi") is not None
            else "."
        ),
        f"Hava keyfiyyeti: {air_quality_label(weather.get('air_quality_us_aqi'), lang)}"
        + (
            f" (US AQI {weather['air_quality_us_aqi']})."
            if weather.get("air_quality_us_aqi") is not None
            else "."
        ),
    )

    return localized(
        lang,
        (
            f"Morning mode is ready. Today is {day_name}, {date_text}. "
            f"Time: {current_time}. Weather in {weather['location']}: {weather['description']}, "
            f"{weather['temp_c']}C now, feels like {weather['feels_like_c']}C, high {weather['max_temp_c']}C, low {weather['min_temp_c']}C. "
            f"{precipitation_line} Wind: {weather['wind_kph']} km/h. Humidity: {weather['humidity']}%. "
            f"Sunrise: {weather['sunrise']}. Sunset: {weather['sunset']}. UV index: {weather['uv_index']}. "
            f"{air_quality_text} What to wear: {outfit_advice(lang, weather)} "
            f"School or work advice: {school_work_advice(lang, weather)} "
            f"Weekly forecast: {weekly_text}"
        ),
        (
            f"Seher rejimi hazirdir. Bugun {day_name}, {date_text}. "
            f"Vaxt: {current_time}. {weather['location']} ucun hava: {weather['description']}, "
            f"indi {weather['temp_c']}C, hiss olunan {weather['feels_like_c']}C, en yuksek {weather['max_temp_c']}C, en asagi {weather['min_temp_c']}C. "
            f"{precipitation_line} Kulek: {weather['wind_kph']} km/s. Rutubet: {weather['humidity']}%. "
            f"Gundogumu: {weather['sunrise']}. Gunbatimi: {weather['sunset']}. UV indeksi: {weather['uv_index']}. "
            f"{air_quality_text} Ne geyinmeli: {outfit_advice(lang, weather)} "
            f"Mekteb ve ya is ucun meslehet: {school_work_advice(lang, weather)} "
            f"Heftelik proqnoz: {weekly_text}"
        ),
    )


def humanize_seconds(seconds):
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{seconds} seconds"


def parse_duration_seconds(text):
    lowered = (text or "").lower()
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
    plain_number = re.search(r"(\d+)\b", lowered)
    if plain_number:
        return int(plain_number.group(1))
    return None


def looks_like_url(target):
    if not target:
        return False
    if target.startswith(("http://", "https://")):
        return True
    return bool(re.match(r"^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}([/?#].*)?$", target))


def resolve_open_target(target):
    cleaned = (target or "").strip().lower()
    for prefix in ("website ", "site ", "the "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    if cleaned in WEBSITE_ALIASES:
        return WEBSITE_ALIASES[cleaned]
    if looks_like_url(cleaned):
        return cleaned if cleaned.startswith(("http://", "https://")) else f"https://{cleaned}"
    return None


def google_search_url(query):
    return f"https://www.google.com/search?q={quote_plus(query)}"


def run_open_request(raw_target, allow_pc_controls):
    url_target = resolve_open_target(raw_target)
    if url_target:
        return open_target(url_target), url_target
    cleaned = (raw_target or "").strip()
    if not cleaned:
        return False, ""
    if not allow_pc_controls:
        return open_target(google_search_url(cleaned)), google_search_url(cleaned)
    if open_target(cleaned):
        return True, cleaned
    return open_target(google_search_url(cleaned)), google_search_url(cleaned)


def combine_responses(responses):
    seen = set()
    combined = []
    for response in responses:
        text = (response or "").strip()
        if text and text not in seen:
            seen.add(text)
            combined.append(text)
    return " ".join(combined)


def plan_ai_commands(user_id, raw_command, lang, allow_pc_controls):
    memory_keys = sorted(MEMORY.get(user_id, {}).get("memory", {}).keys())[:10]
    contact_names = ", ".join(sorted(CONTACTS.keys()))
    prompt = f"""
You are the action planner for an Iron-Man-style assistant named F.R.I.D.A.Y.
Return JSON only with this shape:
{{
  "reply": "short optional reply in {'English' if lang == 'en' else 'Azerbaijani'}",
  "commands": ["canonical command 1", "canonical command 2"]
}}

Rules:
- Use at most {PLAN_COMMAND_LIMIT} commands.
- Only output commands that this assistant can actually execute.
- If the request is conversational or unsupported, leave "commands" empty and put the answer in "reply".
- Prefer direct actions over chatty replies.
- Use PC-only commands only when allow_pc_controls is true.
- Convert timer durations to seconds.
- If the user wants a website, use "open <url or domain>" or "search for <query>".
- If the user wants FRIDAY to say something out loud, use "say <text>".

Allowed canonical commands:
- open <url or app name>
- search for <query>
- close <app name>
- lock pc
- take screenshot
- shutdown pc
- restart pc
- start timer <seconds>
- remind me to <text>
- set weather location to <location>
- morning mode
- study mode
- game mode
- privacy mode
- emergency mode
- show notification summary
- who is here
- enable security mode
- disable security mode
- lights on
- lights off
- open friday site
- check friday site
- remember <key> is <value>
- what do you remember about <key>
- set wake word to <word>
- call <contact>
- message <contact>
- weather
- what to wear
- is it raining
- is it snowing
- sunrise
- sunset
- air quality
- weekly forecast
- school advice
- what time is it
- what day is it
- say <text>

Context:
- allow_pc_controls: {json.dumps(allow_pc_controls)}
- known contacts: {contact_names}
- known memory keys: {", ".join(memory_keys) if memory_keys else "none"}
- user request: {raw_command}
""".strip()
    payload, error = request_json(prompt)
    if error or not isinstance(payload, dict):
        return None
    commands = []
    for item in payload.get("commands", []):
        if not isinstance(item, str):
            continue
        normalized = normalize_command(item)
        if normalized:
            commands.append(normalized)
        if len(commands) >= PLAN_COMMAND_LIMIT:
            break
    reply = payload.get("reply", "")
    if not isinstance(reply, str):
        reply = ""
    return {"commands": commands, "reply": reply.strip()}


def execute_direct_command(user_id, command_text):
    user = USERS[user_id]
    lang = user["language"]
    cmd = normalize_command(command_text)
    data = MEMORY[user_id]
    allow_pc_controls = user_id in {"owner", "senan"}
    if not cmd:
        return localized(lang, "No command received.", "Komanda alinmadi.")
    if cmd in {"help", "what can you do", "what are your abilities"}:
        return localized(
            lang,
            "Ask naturally. I can open apps or websites, search the web, remember details, handle timers and reminders, manage security actions, answer time or weather questions, and chain multiple actions together.",
            "Tebii sekilde iste. Men proqram ve sayt aça, internetde axtaris ede, melumat yadda saxlaye, taymer ve xatirlatma qura, tehlukesizlik hereketlerini idare ede, vaxt ve hava suallarini cavablaya, bir nece hereketi zencir kimi icra ede bilerem.",
        )
    if cmd in {"open google", "google"}:
        return (
            localized(lang, "Opening Google.", "Google acilir.")
            if open_target("https://google.com")
            else localized(lang, "Google could not be opened.", "Google acilmadi.")
        )
    if cmd in {"open spotify", "spotify"}:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        return (
            localized(lang, "Opening Spotify.", "Spotify acilir.")
            if launch_app("spotify")
            else localized(lang, "Spotify could not be opened.", "Spotify acilmadi.")
        )
    if cmd in {"open discord", "discord"}:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        return (
            localized(lang, "Opening Discord.", "Discord acilir.")
            if launch_app("discord")
            else localized(lang, "Discord could not be opened.", "Discord acilmadi.")
        )
    if cmd in {"open roblox", "roblox"}:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        return (
            localized(lang, "Opening Roblox.", "Roblox acilir.")
            if launch_app("roblox")
            else localized(lang, "Roblox could not be opened.", "Roblox acilmadi.")
        )
    if cmd in {"open minecraft", "minecraft"}:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        return (
            localized(lang, "Opening Minecraft.", "Minecraft acilir.")
            if launch_app("minecraft")
            else localized(
                lang, "Minecraft could not be opened.", "Minecraft acilmadi."
            )
        )
    if cmd.startswith("close "):
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        app_name = cmd.replace("close ", "", 1).strip()
        close_named_app(app_name)
        return localized(lang, f"Closing {app_name}.", f"{app_name} baglanir.")
    if "lock pc" in cmd:
        if user_id not in {"owner", "senan"}:
            return localized(
                lang,
                "Only the PC accounts can use that command.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        subprocess.run(
            ["rundll32.exe", "user32.dll,LockWorkStation"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return localized(lang, "PC locked.", "PC kilidlendi.")
    if "take screenshot" in cmd or "screenshot" in cmd:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        file_name = take_screenshot()
        if file_name:
            return localized(
                lang,
                f"Screenshot saved to captures/{file_name}",
                f"Ekran sekli captures/{file_name} olaraq saxlanildi.",
            )
        return localized(lang, "Screenshot failed.", "Ekran sekli alinmadi.")
    if "shutdown pc" in cmd:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        os.system("shutdown /s /t 10")
        return localized(
            lang, "PC will shut down in 10 seconds.", "PC 10 saniyeye sonecek."
        )
    if "restart pc" in cmd:
        if not allow_pc_controls:
            return localized(
                lang,
                "This command is only for the PC accounts.",
                "Bu komanda yalniz PC hesablarina aiddir.",
            )
        os.system("shutdown /r /t 10")
        return localized(
            lang, "PC will restart in 10 seconds.", "PC 10 saniyeye yeniden baslayacaq."
        )
    if "take picture" in cmd:
        return localized(
            lang,
            "Use the camera action to take a picture.",
            "Sekil cekmek ucun kamera hereketini istifade et.",
        )
    if "start recording" in cmd:
        return localized(
            lang,
            "Use the camera action to start recording.",
            "Yazmaga baslamaq ucun kamera hereketini istifade et.",
        )
    if "stop recording" in cmd:
        return localized(
            lang,
            "Use the camera action to stop recording.",
            "Yazmani dayandirmaq ucun kamera hereketini istifade et.",
        )
    if "start scanning" in cmd:
        data["security_mode"] = True
        save_memory()
        return localized(lang, "Scanning mode enabled.", "Skan rejimi aktivdir.")
    if "stop scanning" in cmd:
        data["security_mode"] = False
        save_memory()
        return localized(lang, "Scanning mode disabled.", "Skan rejimi dayandirildi.")
    if cmd.startswith("download mp4 "):
        url = cmd.split("download mp4 ", 1)[1].strip()
        file_name, status = download_mp4_file(url)
        if status == "ok":
            return localized(
                lang,
                f"MP4 saved to downloads/{file_name}",
                f"MP4 downloads/{file_name} kimi saxlanildi.",
            )
        if status == "not_mp4":
            return localized(
                lang, "Use a direct .mp4 link.", "Birbasa .mp4 linki istifade et."
            )
        return localized(lang, "MP4 download failed.", "MP4 yuklenmedi.")
    if cmd.startswith("start timer "):
        seconds = parse_duration_seconds(cmd.replace("start timer", "", 1))
        if not seconds:
            return localized(
                lang, "Timer value is invalid.", "Taymer deyeri yanlisdir."
            )
        run_timer(user_id, seconds)
        return localized(
            lang,
            f"Timer started for {humanize_seconds(seconds)}.",
            f"{humanize_seconds(seconds)} ucun taymer basladi.",
        )
    if cmd.startswith("set a timer for "):
        seconds = parse_duration_seconds(cmd.replace("set a timer for ", "", 1))
        if not seconds:
            return localized(
                lang, "Timer value is invalid.", "Taymer deyeri yanlisdir."
            )
        run_timer(user_id, seconds)
        return localized(
            lang,
            f"Timer started for {humanize_seconds(seconds)}.",
            f"{humanize_seconds(seconds)} ucun taymer basladi.",
        )
    if cmd in {
        "weather",
        "weather report",
        "tell me the weather",
        "how is the weather",
    }:
        weather, error = get_weather_or_error(user_id, lang)
        return error or weather_brief(lang, weather)
    if cmd in {"day", "what day is it", "today", "date"}:
        return localized(
            lang,
            f"Today is {time.strftime('%A, %d %B %Y')}.",
            f"Bugun {time.strftime('%A, %d %B %Y')}.",
        )
    if cmd in {"what to wear", "what should i wear", "wear advice", "clothes"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or localized(
            lang,
            f"What to wear: {outfit_advice(lang, weather)}",
            f"Ne geyinmeli: {outfit_advice(lang, weather)}",
        )
    if cmd in {"is it raining", "rain", "will it rain"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or precipitation_text(lang, weather)
    if cmd in {"is it snowing", "snow", "will it snow"}:
        weather, error = get_weather_or_error(user_id, lang)
        if error:
            return error
        return localized(
            lang,
            f"Snow chance today: {weather['chance_of_snow']}%. {'Snow is possible.' if weather['is_snowing'] else 'Snow is not expected.'}",
            f"Bu gun qar ehtimali: {weather['chance_of_snow']}%. {'Qar ehtimali var.' if weather['is_snowing'] else 'Qar gozlenilmir.'}",
        )
    if cmd in {"sunrise", "when is sunrise"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or localized(
            lang,
            f"Sunrise is at {weather['sunrise']}.",
            f"Gundogumu {weather['sunrise']} vaxtindadir.",
        )
    if cmd in {"sunset", "when is sunset"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or localized(
            lang,
            f"Sunset is at {weather['sunset']}.",
            f"Gunbatimi {weather['sunset']} vaxtindadir.",
        )
    if cmd in {"air quality", "aqi"}:
        weather, error = get_weather_or_error(user_id, lang)
        if error:
            return error
        return localized(
            lang,
            f"Air quality: {air_quality_label(weather.get('air_quality_us_aqi'), lang)}"
            + (
                f" (US AQI {weather['air_quality_us_aqi']})."
                if weather.get("air_quality_us_aqi") is not None
                else "."
            ),
            f"Hava keyfiyyeti: {air_quality_label(weather.get('air_quality_us_aqi'), lang)}"
            + (
                f" (US AQI {weather['air_quality_us_aqi']})."
                if weather.get("air_quality_us_aqi") is not None
                else "."
            ),
        )
    if cmd in {"weekly forecast", "forecast", "week forecast"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or weekly_forecast_text(lang, weather)
    if cmd in {"school advice", "work advice", "school work advice"}:
        weather, error = get_weather_or_error(user_id, lang)
        return error or localized(
            lang,
            f"School or work advice: {school_work_advice(lang, weather)}",
            f"Mekteb ve ya is ucun meslehet: {school_work_advice(lang, weather)}",
        )
    if cmd.startswith("remind me to "):
        reminder_text = cmd.split("remind me to ", 1)[1].strip()
        seconds = None
        if " in " in reminder_text:
            possible_text, possible_delay = reminder_text.rsplit(" in ", 1)
            parsed = parse_duration_seconds(possible_delay)
            if parsed:
                reminder_text = possible_text.strip()
                seconds = parsed
        if not reminder_text:
            return localized(
                lang,
                "Please tell me what to remind you about.",
                "Zehmet olmasa neyi xatirlatmali oldugumu yaz.",
            )
        if seconds:
            run_reminder(user_id, lang, reminder_text, seconds)
            return localized(
                lang,
                f"Reminder set for {humanize_seconds(seconds)}: {reminder_text}.",
                f"{humanize_seconds(seconds)} ucun xatirlatma quruldu: {reminder_text}.",
            )
        add_notification(
            user_id,
            localized(
                lang,
                f"Reminder saved: {reminder_text}.",
                f"Xatirlatma saxlanildi: {reminder_text}.",
            ),
        )
        return localized(
            lang,
            f"Reminder saved: {reminder_text}.",
            f"Xatirlatma saxlanildi: {reminder_text}.",
        )
    if "morning mode" in cmd:
        return morning_mode_report(user_id, lang)
    if cmd.startswith("set weather location to "):
        location = cmd.split("set weather location to ", 1)[1].strip()
        if not location:
            return localized(
                lang,
                "Please provide a weather location.",
                "Zehmet olmasa hava lokasiyasini yaz.",
            )
        data["memory"]["weather location"] = location
        save_memory()
        return localized(
            lang,
            f"Weather location set to {location}.",
            f"Hava lokasiyasi {location} olaraq secildi.",
        )
    if "study mode" in cmd:
        open_target("https://google.com")
        open_target("https://classroom.google.com")
        add_notification(
            user_id, localized(lang, "Study mode started.", "Ders rejimi basladi.")
        )
        return localized(lang, "Study mode started.", "Ders rejimi basladi.")
    if "game mode" in cmd:
        launch_app("discord")
        return localized(lang, "Game mode started.", "Oyun rejimi basladi.")
    if "privacy mode" in cmd:
        for app in ["chrome", "msedge", "opera", "discord", "spotify"]:
            close_named_app(app)
        return localized(lang, "Privacy mode enabled.", "Mexfilik rejimi aktivdir.")
    if "emergency mode" in cmd:
        closed_count = close_other_apps()
        return localized(
            lang,
            f"Emergency mode closed {closed_count} apps.",
            f"Tehlukesizlik rejimi {closed_count} proqram bagladi.",
        )
    if "show notification summary" in cmd:
        notifications = data["notifications"][-5:]
        if not notifications:
            return localized(lang, "No notifications yet.", "Hele bildiris yoxdur.")
        return "; ".join(f'{item["time"]} - {item["text"]}' for item in notifications)
    if "who is here" in cmd:
        last_person = data.get("last_person", {"status": "unknown", "name": ""})
        if last_person.get("status") == "known" and last_person.get("name"):
            return localized(
                lang,
                f'{last_person["name"]} is here.',
                f'{last_person["name"]} buradadir.',
            )
        return t(lang, "who_here_unknown")
    if cmd in {"enable security mode", "security mode on", "turn on security mode"}:
        data["security_mode"] = True
        save_memory()
        return localized(
            lang, "Security mode enabled.", "Tehlukesizlik rejimi aktivdir."
        )
    if cmd in {"disable security mode", "security mode off", "turn off security mode"}:
        data["security_mode"] = False
        save_memory()
        return localized(
            lang, "Security mode disabled.", "Tehlukesizlik rejimi sonduruldu."
        )
    if cmd in {
        "lights on",
        "light on",
        "enable lights",
        "enable light",
        "enable ligths",
        "ligths on",
        "turn on lights",
        "turn on ligths",
    }:
        return localized(
            lang,
            "Light command sent. In the browser app this can only control the current phone if flashlight access is supported.",
            "Isiq komandasi gonderildi. Brauzer app-da bu yalniz cari telefonda, fener desteyi varsa isleyir.",
        )
    if cmd in {
        "lights off",
        "light off",
        "disable lights",
        "disable light",
        "disable ligths",
        "ligths off",
        "turn off lights",
        "turn off ligths",
    }:
        return localized(
            lang,
            "Light off command sent. In the browser app this can only control the current phone if flashlight access is supported.",
            "Isiqi sondurme komandasi gonderildi. Brauzer app-da bu yalniz cari telefonda, fener desteyi varsa isleyir.",
        )
    if "open friday site" in cmd or "open friday app" in cmd:
        return (
            localized(lang, "Opening the FRIDAY site.", "FRIDAY sayti acilir.")
            if open_target(family_public_link())
            else localized(
                lang, "The FRIDAY site could not be opened.", "FRIDAY sayti acilmadi."
            )
        )
    if "check friday site" in cmd or "is friday site online" in cmd:
        return localized(
            lang,
            f"FRIDAY site is online at {family_public_link()}",
            f"FRIDAY sayti aktivdir: {family_public_link()}",
        )
    if "open custom command " in cmd:
        command_name = cmd.split("open custom command ", 1)[1].strip()
        mapped = data["custom_commands"].get(command_name)
        return (
            execute_command(user_id, mapped)
            if mapped
            else localized(
                lang,
                f'Custom command "{command_name}" was not found.',
                f'"{command_name}" adli custom komanda tapilmadi.',
            )
        )
    if cmd.startswith("search for "):
        query = cmd.split("search for ", 1)[1].strip()
        if not query:
            return localized(
                lang,
                "Please tell me what to search for.",
                "Zehmet olmasa ne axtarmali oldugumu yaz.",
            )
        return (
            localized(lang, f"Searching for {query}.", f"{query} ucun axtaris edilir.")
            if open_target(google_search_url(query))
            else localized(lang, "Search could not be opened.", "Axtaris acilmadi.")
        )
    if cmd.startswith("open "):
        target = cmd.split("open ", 1)[1].strip()
        if not target:
            return localized(
                lang,
                "Please tell me what to open.",
                "Zehmet olmasa neyi acmali oldugumu yaz.",
            )
        opened, _ = run_open_request(target, allow_pc_controls)
        if opened:
            return localized(
                lang,
                f"Opening {target}.",
                f"{target} acilir.",
            )
        return localized(
            lang,
            f"I could not open {target}.",
            f"{target} acilmadi.",
        )
    if cmd.startswith("launch "):
        return execute_direct_command(user_id, f"open {cmd.split('launch ', 1)[1]}")
    if cmd.startswith("run "):
        return execute_direct_command(user_id, f"open {cmd.split('run ', 1)[1]}")
    if cmd.startswith("start ") and not cmd.startswith(
        ("start timer", "start scanning", "start recording")
    ):
        return execute_direct_command(user_id, f"open {cmd.split('start ', 1)[1]}")
    if "remember " in cmd and " is " in cmd:
        left, right = cmd.replace("remember ", "", 1).split(" is ", 1)
        key = left.strip()
        value = right.strip()
        data["memory"][key] = value
        save_memory()
        return localized(
            lang,
            f"I will remember that {key} is {value}.",
            f"Yadda saxlayacam ki {key} {value}-dir.",
        )
    if "what do you remember about " in cmd:
        key = cmd.split("what do you remember about ", 1)[1].strip()
        value = data["memory"].get(key)
        if value:
            return localized(
                lang,
                f"You told me {key} is {value}.",
                f"Sen mene demisen ki {key} {value}-dir.",
            )
        return localized(
            lang,
            f"I do not remember anything about {key} yet.",
            f"Hele {key} haqqinda hec ne yadimda yoxdur.",
        )
    if "set wake word to " in cmd:
        wake_word = cmd.split("set wake word to ", 1)[1].strip()
        data["wake_word"] = wake_word
        save_memory()
        return localized(
            lang,
            f"Wake word set to {wake_word}.",
            f"Oyatma sozu {wake_word} olaraq secildi.",
        )
    if cmd.startswith("call "):
        target = cmd.replace("call ", "", 1).strip()
        number = CONTACTS.get(target)
        return (
            localized(
                lang,
                f"Calling {target} at {number}.",
                f"{target} ucun zeng hazirlanir: {number}.",
            )
            if number
            else localized(lang, "Contact not found.", "Elaqe tapilmadi.")
        )
    if cmd.startswith("message "):
        target = cmd.replace("message ", "", 1).strip()
        number = CONTACTS.get(target)
        return (
            localized(
                lang,
                f"Message prepared for {target} at {number}.",
                f"{target} ucun mesaj hazirlandi: {number}.",
            )
            if number
            else localized(lang, "Contact not found.", "Elaqe tapilmadi.")
        )
    if "what time is it" in cmd or cmd == "time":
        return localized(
            lang,
            f"Current time: {time.strftime('%H:%M:%S')}",
            f"Cari vaxt: {time.strftime('%H:%M:%S')}",
        )
    if cmd in {"what day is it", "what date is it"}:
        return localized(
            lang,
            f"Today is {time.strftime('%A, %d %B %Y')}.",
            f"Bugun {time.strftime('%A, %d %B %Y')}.",
        )
    if cmd.startswith("say "):
        text = cmd.split("say ", 1)[1].strip()
        return text or localized(lang, "What should I say?", "Neyi deymeliyem?")
    if "say hello" in cmd or "hello friday" in cmd:
        return localized(
            lang,
            f"Hello {user['display_name']}. {user['assistant_name']} is online.",
            f"Salam {user['display_name']}. {user['assistant_name']} hazirdir.",
        )
    if "shutdown phone" in cmd:
        return localized(
            lang,
            "Phone shutdown is not configured yet.",
            "Telefon sondurme hele qurulmayib.",
        )
    if "lock phone" in cmd:
        return localized(
            lang, "Phone lock is not configured yet.", "Telefon kilidi hele qurulmayib."
        )
    return None


def execute_command(user_id, command_text, allow_ai=True):
    user = USERS[user_id]
    lang = user["language"]
    cmd = normalize_command(command_text)
    allow_pc_controls = user_id in {"owner", "senan"}
    direct_result = execute_direct_command(user_id, cmd)
    if direct_result is not None:
        return direct_result
    if allow_ai:
        plan = plan_ai_commands(user_id, command_text, lang, allow_pc_controls)
        if plan:
            planned_responses = []
            for planned_command in plan["commands"]:
                response = execute_command(user_id, planned_command, allow_ai=False)
                if response is not None:
                    planned_responses.append(response)
            combined = combine_responses(planned_responses)
            if combined:
                return combined
            if plan["reply"]:
                return plan["reply"]
    return localized(
        lang,
        "I heard you, but I do not know how to do that yet.",
        "Seni esidirem, amma bunu hele ede bilmirem.",
    )


class FridayHandler(BaseHTTPRequestHandler):
    def _send_html(self, body, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        headers = no_store_headers()
        if extra_headers:
            headers.update(extra_headers)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        headers = no_store_headers()
        if extra_headers:
            headers.update(extra_headers)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        headers = no_store_headers()
        if extra_headers:
            headers.update(extra_headers)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            session = get_session(self)
            if (
                session
                and session["user_id"] in USERS
                and not USERS[session["user_id"]]["banned"]
            ):
                user_id = session["user_id"]
                self._send_html(control_page(user_id))
                if not MEMORY[user_id].get("tutorial_seen", False):
                    MEMORY[user_id]["tutorial_seen"] = True
                    save_memory()
            else:
                self._send_html(login_page())
            return
        if self.path == "/activity-log":
            session = get_session(self)
            if (
                not session
                or session["user_id"] != "owner"
                or not session.get("activity_unlocked")
            ):
                self._send_json({"ok": False, "message": "Access denied."}, status=403)
                return
            self._send_json({"ok": True, "html": get_owner_activity_html()})
            return
        if self.path == "/status":
            self._send_json(
                {
                    "status": "online",
                    "local_url": LOCAL_URL,
                    "family_url": f"http://{get_local_ip()}:{PORT}",
                    "public_url": get_public_url(),
                }
            )
            return
        if self.path == "/logout":
            raw_cookie = self.headers.get("Cookie")
            if raw_cookie:
                jar = cookies.SimpleCookie()
                jar.load(raw_cookie)
                item = jar.get("friday_session")
                if item:
                    SESSIONS.pop(item.value, None)
            self._redirect(
                "/",
                {
                    "Set-Cookie": "friday_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"
                },
            )
            return
        self._send_html(b"<h1>Not found</h1>", status=404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        if self.path == "/login":
            fields = parse_qs(body.decode("utf-8"))
            password = fields.get("password", [""])[0]
            user_id, user = find_user_by_password(password)
            if user is None:
                self._send_html(login_page("Wrong password."))
                return
            if user["banned"]:
                self._send_html(
                    login_page("Access blocked. You are banned by the owner.")
                )
                return
            token = secrets.token_urlsafe(24)
            SESSIONS[token] = {"user_id": user_id}
            add_activity(
                user_id,
                (
                    "Logged in."
                    if USERS[user_id]["language"] == "en"
                    else "Hesaba daxil oldu."
                ),
            )
            self._redirect(
                "/",
                {
                    "Set-Cookie": f"friday_session={token}; Path=/; HttpOnly; SameSite=Strict"
                },
            )
            return
        if self.path == "/camera-status":
            session = get_session(self)
            if (
                not session
                or session["user_id"] not in USERS
                or USERS[session["user_id"]]["banned"]
            ):
                self._send_json({"status": "unknown"}, status=401)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json({"status": "unknown"}, status=400)
                return
            self._send_json(detect_person(decode_data_url(payload.get("image", ""))))
            return
        if self.path == "/transcribe-audio":
            session = get_session(self)
            if (
                not session
                or session["user_id"] not in USERS
                or USERS[session["user_id"]]["banned"]
            ):
                self._send_json({"ok": False, "message": "Access denied."}, status=401)
                return
            text, error = transcribe_wav_bytes(
                body, USERS[session["user_id"]]["language"]
            )
            if error:
                self._send_json({"ok": False, "message": error, "text": ""}, status=400)
                return
            self._send_json({"ok": True, "text": text})
            return
        if self.path == "/activity-unlock":
            session = get_session(self)
            if not session or session["user_id"] != "owner":
                self._send_json({"ok": False, "message": "Access denied."}, status=403)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(
                    {"ok": False, "message": "Invalid request."}, status=400
                )
                return
            if payload.get("password", "") != ACTIVITY_PASSWORD:
                self._send_json({"ok": False, "message": "Wrong password."}, status=403)
                return
            session["activity_unlocked"] = True
            self._send_json({"ok": True})
            return
        if self.path == "/admin/toggle-ban":
            session = get_session(self)
            if not session or not USERS.get(session["user_id"], {}).get("is_admin"):
                self._send_json({"ok": False, "message": "Access denied."}, status=403)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(
                    {"ok": False, "message": "Invalid request."}, status=400
                )
                return
            target_id = payload.get("user_id", "")
            if target_id not in USERS or USERS[target_id].get("is_admin"):
                self._send_json(
                    {"ok": False, "message": "Cannot change that account."}, status=400
                )
                return
            USERS[target_id]["banned"] = not USERS[target_id]["banned"]
            save_users()
            for token, token_session in list(SESSIONS.items()):
                if token_session["user_id"] == target_id and USERS[target_id]["banned"]:
                    SESSIONS.pop(token, None)
            self._send_json({"ok": True, "message": "Status updated."})
            return
        if self.path == "/command":
            session = get_session(self)
            if not session or session["user_id"] not in USERS:
                self._send_json({"message": "Access denied."}, status=401)
                return
            if USERS[session["user_id"]]["banned"]:
                self._send_json({"message": "Access blocked."}, status=403)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json({"message": "Invalid request."}, status=400)
                return
            raw_command = payload.get("command", "")
            if raw_command:
                add_message(session["user_id"], "You", raw_command)
                add_activity(session["user_id"], f"Command: {raw_command}")
            answer = execute_command(session["user_id"], raw_command)
            add_message(session["user_id"], "Assistant", answer)
            self._send_json({"message": answer})
            return
        self._send_json({"message": "Not found."}, status=404)


def open_browser():
    time.sleep(1.5)
    webbrowser.open(LOCAL_URL)


if __name__ == "__main__":
    load_known_faces()
    threading.Thread(target=open_browser, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), FridayHandler)
    print(f"FRIDAY browser app running at {LOCAL_URL}")
    print(f"Family Wi-Fi link: http://{get_local_ip()}:{PORT}")
    public_url = get_public_url()
    if public_url:
        print(f"Public link: {public_url}")
    server.serve_forever()
