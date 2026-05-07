import os, cv2, time, datetime, threading, webbrowser, subprocess
import pyttsx3, speech_recognition as sr

# -------------------- AI SAFE MODE --------------------
AI_ENABLED = False
try:
    import google.genai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        AI_ENABLED = True
except:
    AI_ENABLED = False

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


# -------------------- SECURITY --------------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
security_mode = False


def capture(frame):
    os.makedirs("captures", exist_ok=True)
    t = datetime.datetime.now().strftime("%H%M%S")
    cv2.imwrite(f"captures/photo_{t}.jpg", frame)


def camera_loop():
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)

        if security_mode and len(faces) > 0:
            speak("Unknown person detected")
            capture(frame)

        cv2.imshow("FRIDAY Camera", frame)

        if cv2.waitKey(1) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


# -------------------- AI RESPONSE --------------------
def ai_response(text):
    if not AI_ENABLED:
        return None
    try:
        r = client.models.generate_content(model="gemini-2.5-flash", contents=text)
        return r.text
    except:
        return None


# -------------------- COMMAND SYSTEM --------------------
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
        # ONLY try AI if available
        response = ai_response(cmd)
        if response:
            speak(response)
        else:
            speak("Command not recognized")


# -------------------- MAIN --------------------
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
