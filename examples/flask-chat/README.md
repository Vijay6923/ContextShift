# ContextShift example: Flask chat app

A small, real Flask chat application — streaming chat, PDF upload, image
analysis, pinning, and summarization — demonstrating `contextshift` used
in a real product rather than a code snippet. All context-management
decisions route through `contextshift/` via [`adapters.py`](adapters.py);
nothing here reimplements what the library already does.

This app is a *consumer* of ContextShift, not part of the framework
itself — it lives here, under `examples/`, rather than at the repository
root, so a stranger cloning the repo sees the library first.

## Running it

From this directory:

Run from *this* directory (`examples/flask-chat/`), not the repository
root — `requirements.txt` installs `contextshift` itself, editable,
from the parent checkout (`-e ../..`), which only resolves correctly
relative to this directory:

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY and GEMINI_API_KEY
python app.py
```

Open `http://localhost:5000`. A live deployment also runs at
[context-shift.vercel.app](https://context-shift.vercel.app/).

| Variable | Required | Used for |
|---|---|---|
| `GROQ_API_KEY` | Yes | Chat and summarization, via `GroqProvider` |
| `GEMINI_API_KEY` | Only for image upload | Image understanding, via `GeminiVisionProvider` |
| `FLASK_DEBUG` | No (default `true`) | Flask debug/reload mode |
| `FLASK_PORT` | No (default `5000`) | Port the app listens on |
| `DATABASE_URL` | No (defaults to local SQLite) | Database connection string |

## Running its tests

```bash
pip install -r requirements-dev.txt   # from the repository root
pytest examples/flask-chat/tests/
```

These are route-level and integration tests for this app specifically —
distinct from `tests/` at the repository root, which tests
`contextshift/` itself and needs no Flask app, database, or HTTP client
to run.

## Deploying to Vercel

[`vercel.json`](vercel.json) and [`api/index.py`](api/index.py) are
already set up for a serverless deployment — but because this app no
longer lives at the repository root, set this directory
(`examples/flask-chat`) as the **Root Directory** in your Vercel
project settings (Project Settings → General → Root Directory), rather
than deploying from the repository root.

## Files

```
app.py          Flask routes: /chat, /messages, /pin, /prune, /upload, ...
adapters.py     Translates between ORM Message rows and contextshift's
                Message/ContextManager -- the only file that imports
                both `models` and `contextshift`.
models.py       SQLAlchemy Message model.
config.py       Flask app configuration (API keys, database URL, budget).
templates/,
static/         The chat UI.
api/, vercel.json  Vercel serverless deployment entrypoint.
```
