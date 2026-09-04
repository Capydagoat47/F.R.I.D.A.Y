# FRIDAY AI HUD

FRIDAY is a cinematic Iron Man style browser assistant with secure server-side Gemini integration, browser voice control, wake-word activation, session memory, safe command routing, PWA install support, and Capacitor Android wrapper support.

## Run Locally

1. Create or update `.env`:

```text
GEMINI_API_KEY=your_api_key_here
FRIDAY_AI_MODEL=gpt-5
PORT=5000
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Start FRIDAY:

```powershell
python server.py
```

4. Open `http://127.0.0.1:5000`.

## Voice And Wake Word

Click `Voice` once to grant microphone access. With wake mode armed, say `FRIDAY` or `Hey Friday` followed by a command. FRIDAY auto-restarts browser speech recognition when it stops and falls back to server transcription when browser recognition is unavailable.

If the browser speech engine is flaky, FRIDAY now records your microphone input locally, sends it to `/api/transcribe`, and uses that transcript to answer your command.

## Safe Commands

Supported local command classes:

- Chat and memory: notes, facts, tasks, history summary
- Web links: `open YouTube`, `open GitHub`, `open https://example.com`
- Web search: `search web for capacitor android build`
- Time/date and telemetry: `current time`, `system status`
- Timers and reminders
- Simulated HUD modes: power, security, lock, vision status

The web HUD does not launch arbitrary executables, terminate processes, or run destructive OS power commands.

## PWA

The app includes `manifest.json`, `service-worker.js`, and an installable icon. Open FRIDAY in a Chromium browser, then use `Install app` or `Add to Home Screen`. The service worker caches the UI shell for offline startup; live AI, telemetry, and transcription require the local server.

## Android APK Wrapper

Install Node.js, Android Studio, and the Android SDK first.

```powershell
npm install
npx cap add android
npx cap sync android
npx cap open android
```

In Android Studio, build the APK from the generated `android` project. For a local Python backend during development, point the WebView/server strategy at the machine running `server.py`, or package FRIDAY as a PWA-style WebView shell and keep GEMINI calls on a secure backend you control.
