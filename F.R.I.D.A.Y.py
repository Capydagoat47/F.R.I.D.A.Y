print("FRIDAY LOADING...")

import datetime
import os
import re
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import pyttsx3
import requests
import speech_recognition as sr

from friday_ai import request_json

try:
    import cv2
except Exception:
    cv2 = None

try:
    import face_recognition
except Exception:
    face_recognition = None

# -------------------- CONFIG --------------------
BASE_DIR = Path(__file__).resolve().parent
SERVER_URL = "http://192.168.0.127"
FRIDAY_SITE_URL = "http://127.0.0.1:5000"
KNOWN_FACES_DIR = BASE_DIR / "known_faces"
PHOTO_DIR = BASE_DIR / "captures"
PHOTO_DIR.mkdir(exist_ok=True)

ALLOWED_PEOPLE_IMAGES = {
    "Kenan": KNOWN_FACES_DIR / "Kenan.jpg",
    "Dad": KNOWN_FACES_DIR / "Dad.jpg",
}

WEBSITE_ALIASES = {
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "classroom": "https://classroom.google.com",
    "google classroom": "https://classroom.google.com",
    "friday site": FRIDAY_SITE_URL,
    "friday app": FRIDAY_SITE_URL,
}

PLAN_COMMAND_LIMIT = 4


# -------------------- ALERT FUNCTION --------------------
def send_alert(message):
    try:
        requests.post(f"{SERVER_URL}/alert", json={"msg": message}, timeout=3)
    except Exception:
        pass


def open_friday_site():
    open_target(FRIDAY_SITE_URL)
    return "Opening the FRIDAY site."


def check_friday_site():
    try:
        response = requests.get(f"{FRIDAY_SITE_URL}/status", timeout=3)
        if response.ok:
            return "The FRIDAY site is online."
        return "The FRIDAY site is not responding correctly."
    except Exception:
        return "The FRIDAY site is offline."


# -------------------- VOICE --------------------
try:
    engine = pyttsx3.init()
    engine.setProperty("rate", 170)
except Exception:
    engine = None
recognizer = sr.Recognizer()


def speak(text):
    print("FRIDAY:", text)
    if engine is None:
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


def listen():
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source, phrase_time_limit=6)
        try:
            return recognizer.recognize_google(audio).lower()
        except Exception:
            return ""


# -------------------- CONTACTS --------------------
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


def call(name):
    number = CONTACTS.get(name)
    if number:
        return f"Calling {name} at {number}."
    return "Contact not found."


def message_contact(name):
    number = CONTACTS.get(name)
    if number:
        return f"Message prepared for {name} at {number}."
    return "Contact not found."


# -------------------- TIMER & REMINDER --------------------
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


def timer(seconds):
    def run():
        time.sleep(seconds)
        speak(f"Timer finished after {humanize_seconds(seconds)}.")

    threading.Thread(target=run, daemon=True).start()


def reminder(message, seconds):
    def run():
        time.sleep(seconds)
        speak(f"Reminder: {message}")

    threading.Thread(target=run, daemon=True).start()


# -------------------- FACE RECOGNITION --------------------
allowed_encodings = []
allowed_names = []

for name, path in ALLOWED_PEOPLE_IMAGES.items():
    if face_recognition is not None and path.exists():
        image = face_recognition.load_image_file(str(path))
        encodings = face_recognition.face_encodings(image)
        if encodings:
            allowed_encodings.append(encodings[0])
            allowed_names.append(name)

security_mode = False


def capture(frame):
    if cv2 is None:
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(str(PHOTO_DIR / f"photo_{timestamp}.jpg"), frame)


def camera_loop():
    global security_mode
    if cv2 is None or face_recognition is None:
        print("Camera security disabled: missing OpenCV or face_recognition.")
        return
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding, face_loc in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(allowed_encodings, face_encoding)
            if True not in matches:
                if security_mode:
                    speak("Unknown person detected.")
                    capture(frame)
                    send_alert("Unknown person detected by FRIDAY.")
                top, right, bottom, left = face_loc
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            else:
                name = allowed_names[matches.index(True)]
                cv2.rectangle(
                    frame,
                    (face_loc[3], face_loc[0]),
                    (face_loc[1], face_loc[2]),
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    frame,
                    name,
                    (face_loc[3], face_loc[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

        cv2.imshow("FRIDAY Camera", frame)
        if cv2.waitKey(1) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


# -------------------- ACTION HELPERS --------------------
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


def take_screenshot():
    file_path = PHOTO_DIR / f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
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
        return file_path if file_path.exists() else None
    except Exception:
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
    from urllib.parse import quote_plus

    return f"https://www.google.com/search?q={quote_plus(query)}"


def open_request(target):
    resolved = resolve_open_target(target)
    if resolved:
        return open_target(resolved)
    if open_target(target):
        return True
    return open_target(google_search_url(target))


def normalize_command(cmd):
    cmd = cmd.lower().replace(",", " ").replace("?", " ").strip()
    filler_phrases = [
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
        for phrase in filler_phrases:
            if cmd.startswith(phrase + " "):
                cmd = cmd[len(phrase) :].strip()
                changed = True

    return " ".join(cmd.split())


def combine_responses(responses):
    seen = set()
    combined = []
    for response in responses:
        text = (response or "").strip()
        if text and text not in seen:
            seen.add(text)
            combined.append(text)
    return " ".join(combined)


# -------------------- AI PLANNER --------------------
def plan_ai_commands(raw_command):
    prompt = f"""
You are the action planner for an Iron-Man-style desktop assistant named F.R.I.D.A.Y.
Return JSON only:
{{
  "reply": "short optional reply",
  "commands": ["canonical command 1", "canonical command 2"]
}}

Rules:
- Use at most {PLAN_COMMAND_LIMIT} commands.
- Only output commands from the allowed list below.
- If the request is unsupported or purely conversational, leave "commands" empty and put the answer in "reply".
- Convert timer durations to seconds.
- Prefer direct actions over extra explanation.

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
- open friday site
- check friday site
- enable security mode
- disable security mode
- call <contact>
- message <contact>
- what time is it
- what day is it
- say <text>

Known contacts: {", ".join(sorted(CONTACTS.keys()))}
User request: {raw_command}
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


# -------------------- COMMAND EXECUTION --------------------
def execute_direct_command(cmd):
    global security_mode

    cmd = normalize_command(cmd)
    print("Processed:", cmd)

    if cmd == "":
        return "Yes Boss?"

    if cmd in {"help", "what can you do", "what are your abilities"}:
        return (
            "Ask naturally. I can open apps or websites, search the web, handle timers and reminders, "
            "lock the PC, take screenshots, manage security mode, and chain actions together."
        )

    if "lockdown" in cmd or cmd in {"enable security mode", "security mode on"}:
        security_mode = True
        return "Security mode activated."

    if cmd in {"unlock", "disable security mode", "security mode off"}:
        security_mode = False
        return "Security mode disabled."

    if "start scanning" in cmd:
        security_mode = True
        return "Scanning started."

    if "stop scanning" in cmd:
        security_mode = False
        return "Scanning stopped."

    if "what time is it" in cmd or cmd == "time":
        return f"The time is {datetime.datetime.now().strftime('%H:%M:%S')}."

    if cmd in {"what day is it", "what date is it", "date", "today"}:
        return f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}."

    if "open friday site" in cmd or "open friday app" in cmd:
        return open_friday_site()

    if "check friday site" in cmd or "is friday site online" in cmd:
        return check_friday_site()

    if "take screenshot" in cmd or cmd == "screenshot":
        file_path = take_screenshot()
        if file_path:
            return f"Screenshot saved to {file_path.name}."
        return "Screenshot failed."

    if "shutdown pc" in cmd:
        os.system("shutdown /s /t 10")
        return "PC will shut down in 10 seconds."

    if "restart pc" in cmd:
        os.system("shutdown /r /t 10")
        return "PC will restart in 10 seconds."

    if "lock pc" in cmd:
        subprocess.run(
            ["rundll32.exe", "user32.dll,LockWorkStation"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "PC locked."

    if cmd.startswith("search for "):
        query = cmd.split("search for ", 1)[1].strip()
        if not query:
            return "Tell me what to search for."
        return (
            f"Searching for {query}."
            if open_target(google_search_url(query))
            else "Search could not be opened."
        )

    if cmd.startswith("close "):
        app_name = cmd.split("close ", 1)[1].strip()
        if not app_name:
            return "Tell me what to close."
        close_named_app(app_name)
        return f"Closing {app_name}."

    if cmd.startswith("start timer "):
        seconds = parse_duration_seconds(cmd.replace("start timer", "", 1))
        if not seconds:
            return "Invalid timer."
        timer(seconds)
        return f"Timer started for {humanize_seconds(seconds)}."

    if cmd.startswith("set a timer for "):
        seconds = parse_duration_seconds(cmd.replace("set a timer for ", "", 1))
        if not seconds:
            return "Invalid timer."
        timer(seconds)
        return f"Timer started for {humanize_seconds(seconds)}."

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
            return "Tell me what to remind you about."
        if seconds:
            reminder(reminder_text, seconds)
            return f"Reminder set for {humanize_seconds(seconds)}: {reminder_text}."
        reminder(reminder_text, 10)
        return f"Quick reminder scheduled: {reminder_text}."

    if cmd.startswith("call "):
        return call(cmd.split("call ", 1)[1].strip())

    if cmd.startswith("message "):
        return message_contact(cmd.split("message ", 1)[1].strip())

    if cmd.startswith("say "):
        text = cmd.split("say ", 1)[1].strip()
        return text or "What should I say?"

    if "say hello" in cmd or "hello friday" in cmd:
        return "Hello Boss. FRIDAY is online."

    if cmd.startswith("open "):
        target = cmd.split("open ", 1)[1].strip()
        if not target:
            return "Tell me what to open."
        return f"Opening {target}." if open_request(target) else f"I could not open {target}."

    if cmd.startswith("launch "):
        return execute_direct_command(f"open {cmd.split('launch ', 1)[1]}")

    if cmd.startswith("run "):
        return execute_direct_command(f"open {cmd.split('run ', 1)[1]}")

    if cmd.startswith("start ") and not cmd.startswith(
        ("start timer", "start scanning")
    ):
        return execute_direct_command(f"open {cmd.split('start ', 1)[1]}")

    return None


def execute(cmd, allow_ai=True):
    direct_result = execute_direct_command(cmd)
    if direct_result is not None:
        speak(direct_result)
        return

    if allow_ai:
        plan = plan_ai_commands(cmd)
        if plan:
            planned_responses = []
            for planned_command in plan["commands"]:
                result = execute_direct_command(planned_command)
                if result is not None:
                    planned_responses.append(result)
            combined = combine_responses(planned_responses)
            if combined:
                speak(combined)
                return
            if plan["reply"]:
                speak(plan["reply"])
                return

    speak("I heard you, but I do not know how to do that yet.")


# -------------------- MAIN LOOP --------------------
def main():
    speak("FRIDAY online and ready, Boss.")
    threading.Thread(target=camera_loop, daemon=True).start()

    while True:
        cmd = listen()
        if not cmd:
            continue

        print("You:", cmd)
        if cmd in ["exit", "quit", "stop"]:
            speak("Goodbye Boss.")
            break

        execute(cmd)


if __name__ == "__main__":
    main()
