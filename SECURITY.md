# Security

## OpenAI API Key

Never commit a real OpenAI API key to GitHub. FRIDAY reads the key only from the backend environment:

```text
OPENAI_API_KEY=...
```

For Render, set `OPENAI_API_KEY` in:

`Render Dashboard -> Service -> Environment -> Add Environment Variable`

Do not put the key in `app.js`, `index.html`, `manifest.json`, `service-worker.js`, `README.md`, or any committed file.

## If A Key Was Committed

1. Revoke the exposed key in the OpenAI dashboard.
2. Create a new key.
3. Put the new key only in Render Environment Variables or a local untracked `.env`.
4. Remove `.env` from Git tracking:

```powershell
git rm --cached .env
git commit -m "Remove local environment secrets"
```

If GitHub still blocks the push, the old key is in commit history. Rotate the key first, then remove the secret from history with GitHub secret-scanning guidance or create a clean repository from the current files.
