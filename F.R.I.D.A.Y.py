print("🚀FRIDAY LOADING...")

import os, cv2, time, datetime, threading, webbrowser, subprocess
import pyttsx3, speech_recognition as sr
import face_recognition   
import numpy as np
import requests

# -------------------- CONFIG --------------------
SERVER_URL = "http://192.168.0.127"  # Optional phone notifications
FRIDAY_SITE_URL = "http://127.0.0.1:5000"
ALLOWED_PEOPLE_IMAGES = {
    "Kenan": "knownfaces/kenan.jpg",
    "Dad": "knownfaces/dad.jpg",
}
PHOTO_DIR = "captures"
os.makedirs(PHOTO_DIR, exist_ok=True)


# -------------------- ALERT FUNCTION --------------------
def send_alert(message):
    try:
        requests.post(f"{SERVER_URL}/alert", json={"msg": message})
    except:
        pass


def open_friday_site():
    webbrowser.open(FRIDAY_SITE_URL)
    speak("Opening the FRIDAY site")


def check_friday_site():
    try:
        response = requests.get(f"{FRIDAY_SITE_URL}/status", timeout=3)
        if response.ok:
            speak("The FRIDAY site is online")
        else:
            speak("The FRIDAY site is not responding correctly")
    except:
        speak("The FRIDAY site is offline")


# -------------------- VOICE --------------------
engine = pyttsx3.init()
engine.setProperty("rate", 170)
recognizer = sr.Recognizer()


def speak(text):
    print("FRIDAY:", text)
    engine.say(text)
    engine.runAndWait()


def listen():
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source, phrase_time_limit=5)
        try:
            return recognizer.recognize_google(audio).lower()
        except:
            return ""


# -------------------- CONTACTS --------------------
contacts = {
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
    if name in contacts:
        speak(f"Calling {name}")
    else:
        speak("Contact not found")


def message(name):
    if name in contacts:
        speak(f"Message sent to {name}")
    else:
        speak("Contact not found")


# -------------------- TIMER & REMINDER --------------------
def timer(sec):
    def run():
        time.sleep(sec)
        speak("Timer finished")

    threading.Thread(target=run).start()


def reminder(msg, sec):
    def run():
        time.sleep(sec)
        speak(f"Reminder: {msg}")

    threading.Thread(target=run).start()


# -------------------- FACE RECOGNITION --------------------
allowed_encodings = []
allowed_names = []

for name, path in ALLOWED_PEOPLE_IMAGES.items():
    if os.path.exists(path):
        img = face_recognition.load_image_file(path)
        enc = face_recognition.face_encodings(img)
        if enc:
            allowed_encodings.append(enc[0])
            allowed_names.append(name)

security_mode = False


def capture(frame):
    t = datetime.datetime.now().strftime("%H%M%S")
    cv2.imwrite(f"{PHOTO_DIR}/photo_{t}.jpg", frame)


def camera_loop():
    global security_mode
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
                    speak("Unknown person detected!")
                    capture(frame)
                    send_alert("Unknown person detected by FRIDAY!")
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


# -------------------- COMMAND EXECUTION --------------------
def normalize_command(cmd):
    cmd = cmd.lower().replace(",", " ").strip()
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


def execute(cmd):
    global security_mode
    cmd = normalize_command(cmd)
    print("Processed:", cmd)

    if cmd == "":
        speak("Yes Boss?")
        return

    elif "lockdown" in cmd:
        security_mode = True
        speak("Lockdown mode activated")

    elif "unlock" in cmd:
        security_mode = False
        speak("System unlocked")

    elif "start scanning" in cmd:
        security_mode = True
        speak("Scanning started")

    elif "stop scanning" in cmd:
        security_mode = False
        speak("Scanning stopped")

    elif "time" in cmd:
        speak(datetime.datetime.now().strftime("%H:%M"))

    elif "open youtube" in cmd:
        webbrowser.open("https://youtube.com")

    elif "open google" in cmd:
        webbrowser.open("https://google.com")

    elif "open friday site" in cmd or "open friday app" in cmd:
        open_friday_site()

    elif "check friday site" in cmd or "is friday site online" in cmd:
        check_friday_site()

    elif "open" in cmd:
        app = cmd.replace("open ", "")
        subprocess.Popen(app, shell=True)

    elif "close" in cmd:
        app = cmd.replace("close ", "")
        os.system(f"taskkill /im {app}.exe /f")

    elif "lock pc" in cmd:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation")

    elif "call" in cmd:
        call(cmd.replace("call ", ""))

    elif "message" in cmd:
        message(cmd.replace("message ", ""))

    elif "timer" in cmd:
        try:
            sec = int(cmd.split()[-1])
            timer(sec)
        except:
            speak("Invalid timer")

    elif "remind" in cmd:
        reminder("Task", 10)

    else:
        speak("Command not recognized")


# -------------------- MAIN LOOP --------------------
def main():
    speak("FRIDAY online and ready, Boss")
    threading.Thread(target=camera_loop, daemon=True).start()

    while True:
        cmd = listen()
        if not cmd:
            continue

        print("You:", cmd)
        if cmd in ["exit", "quit", "stop"]:
            speak("Goodbye Boss")
            break

        execute(cmd)


if __name__ == "__main__":
    main()
