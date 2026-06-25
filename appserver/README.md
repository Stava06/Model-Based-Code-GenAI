# App Server

Flask backend for Model-Based Code GenAI. Exposes user authentication, OPL file storage, and an agent-driven code generation pipeline powered by **Google ADK** and **Gemini**.

## Stack

- **Flask 3** + **flask-cors**
- **MongoDB** (pymongo) — users, OPL documents, logic maps, evaluation scores
- **google-adk** — agent runner, tools, sessions
- **google-genai** — Gemini model calls

## Project structure

```
appserver/
├── app.py                  # Flask entry point
├── config.py               # .env loader (singleton)
├── extensions.py           # MongoDB initialization
├── messages.py             # Structured console logging
├── requirements.txt
├── api/
│   ├── users.py            # /users — auth & profiles
│   ├── files.py            # /file  — OPL save & evaluation
│   └── agent_api.py        # /agent — SSE generation & download
├── agent/
│   ├── agent.py            # ADK agent & runner factory
│   ├── roles.py            # Supervisor / Generator / Critic instructions
│   ├── tools.py            # Tool implementations (ADK function tools)
│   ├── memory.py           # MongoDB data access
│   └── agent_tools/        # Code generation, coverage, execution checks
└── services/
    ├── progress_tracker.py # SSE activity log from agent events
    ├── zip_cache.py        # Short-lived in-memory zip storage
    └── maps.py             # Progress step labels & weights
```

## Setup

### 1. Install dependencies

```bash
cd appserver
pip install -r requirements.txt
```

### 2. Environment variables

Create `.env` in this directory:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URL` | Yes | MongoDB connection string |
| `MONGO_DB` | Yes | Database name |
| `MONGO_USER_COLLECTION` | Yes | Users collection |
| `MONGO_OPL_COLLECTION` | Yes | Saved OPL documents |
| `MONGO_OPL_LOGIC_MAP_COLLECTION` | Yes | OPL logic maps |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Model id (default: `gemini-3.1-flash-lite`) |
| `GEMINI_APP_NAME` | No | ADK app name (default: `model_based_codegen`) |
| `PORT` | No | Listen port (default: `5000`) |
| `FLASK_DEBUG` | No | Flask debug mode (default: `false`) |

### 3. Run

```bash
python app.py
```

The server binds to `0.0.0.0` and auto-increments the port if the configured one is already in use.

For production:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

> **Note:** The in-memory zip cache is per-process. Multiple gunicorn workers each hold separate caches — use a single worker or replace `ZIPCache` with a shared store for multi-worker deployments.

## API reference

### Root

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Server health and config summary |

### Users — `/users`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/` | Users service health |
| `GET` | `/users/list` | List all users |
| `GET` | `/users/login` | Login (`email`, `password` query params) |
| `POST` | `/users/register` | Register (`name`, `email`, `password` body) |
| `GET` | `/users/<email>` | Get user by email |

### Files — `/file`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/file/` | Files service health |
| `POST` | `/file/save` | Save OPL (`opl`, `user_id`, `file_name`) |
| `GET` | `/file/evaluation/<opl_id>` | Evaluation scores for a saved OPL |

### Agent — `/agent`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agent/` | Agent + Gemini health check |
| `GET` | `/agent/generate` | **SSE** — stream generation progress |
| `GET` | `/agent/generate/download` | Download generated zip by `download_id` |

#### `GET /agent/generate` (SSE)

Query parameters:

| Param | Description |
|-------|-------------|
| `opl_id` | MongoDB id of the saved OPL |
| `user_id` | Requesting user id (scopes the download) |
| `filename` | Suggested zip filename (default: `generated_project.zip`) |

Event types emitted as `data: {json}\n\n`:

| `type` | Description |
|--------|-------------|
| `progress` | Activity log update (`activities`, `message`, `step_weights`) |
| `done` | Generation complete — includes `download_id` and `filename` |
| `error` | Generation failed — includes `message` |

The stream uses `Connection: close` so clients can release the connection before fetching the zip.

#### `GET /agent/generate/download`

Query parameters:

| Param | Description |
|-------|-------------|
| `download_id` | Id from the `done` event |
| `user_id` | Must match the user who triggered generation |

Returns `application/zip` on success. Entries expire after **15 minutes**.

## Agent pipeline

The agent is built with Google ADK (`agent/agent.py`) and follows a Supervisor → Generator → Critic loop:

1. **Supervisor** loads the OPL and delegates to the Generator
2. **Generator** creates an OPL logic map, sets a project name, and calls `generate_code` to produce a base64-encoded zip (`frontend/` + `backend/`)
3. **Critic** runs `generate_code_evaluation` — graph coverage, syntax checks, and static execution-readiness tests
4. **Supervisor** calls `finish_and_return_user` when the evaluation passes the score threshold

Progress is tracked by `GenerationProgressTracker`, which maps ADK tool calls to UI steps defined in `services/maps.py`.

### Generated project layout

Each zip contains:

```
project/
├── frontend/          # React + Vite + axios service layer
│   ├── src/App.jsx
│   ├── src/service.js
│   └── package.json
└── backend/           # Flask + CORS API
    ├── app.py
    └── requirements.txt
```

## Health checks

```bash
# Server
curl http://localhost:5000/

# Agent (checks API key, Gemini reachability, ADK agent load)
curl http://localhost:5000/agent/

# Files / MongoDB
curl http://localhost:5000/file/
```

## Development

- Agent OPL examples live in `agent/opl_examples/`
- Training context files in `agent/train/`
- Evaluation and logic-map examples in `agent/examples/`
- Console output uses structured messages from `messages.py` (`SUCCESS`, `ERROR`, `NOTE`, etc.)

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Agent is not loaded` on `/agent/` | Missing/invalid `GEMINI_API_KEY` or ADK import error |
| `Database not configured` on `/file/` | `MONGO_URL` not set or MongoDB unreachable |
| Download returns 404 | Zip expired (15 min TTL) or wrong `user_id` |
| Generation retries 3 times | Agent session missing `generated_code_zip` — check Gemini quota and agent logs |
| Port keeps incrementing | Another process is using the configured `PORT` |
