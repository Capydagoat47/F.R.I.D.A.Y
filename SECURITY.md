# Security

## Gemini API Key

Never commit a real GEMINI API key to GitHub. FRIDAY reads the key only from the backend environment:

```text
GEMINI_API_KEY=...
```

For Render, set `GEMINI_API_KEY` in:

`Render Dashboard -> Service -> Environment -> Add Environment Variable`

Do not put the key in `app.js`, `index.html`, `manifest.json`, `service-worker.js`, `README.md`, or any committed file.

```powershell
git rm --cached .env
git commit -m "Remove local environment secrets"
```

If GitHub still blocks the push, the old key is in commit history. Rotate the key first, then remove the secret from history with GitHub secret-scanning guidance or create a clean repository from the current files.
