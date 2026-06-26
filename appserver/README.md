# App Server

Flask backend for Model-Based Code GenAI. Exposes user authentication, OPL file storage, and an agent-driven code generation pipeline powered by **Google ADK** and **Gemini**.

## Stack

- **Flask 3** + **flask-cors**
- **MongoDB** (pymongo) — users, OPL documents, logic maps, evaluation scores
- **google-adk** — agent runner, tools, sessions
- **google-genai** — Gemini model calls
- **esprima2** — JavaScript/JSX syntax validation in the Critic (pure Python, no Node)

## Project structure

```
appserver/
├── app.py                  # Flask entry point
├── config.py               # .env loader (singleton)
├── extensions.py             # MongoDB + Gemini helpers
├── messages.py               # Structured console logging
├── requirements.txt
├── api/
│   ├── users.py              # /users — auth & profiles
│   ├── files.py              # /file  — OPL save & evaluation
│   └── agent_api.py          # /agent — SSE generation & download
├── agent/
│   ├── agent.py              # ADK agent & runner factory
│   ├── roles.py              # Supervisor / Generator / Critic instructions
│   ├── memory.py             # MongoDB data access
│   ├── tools/
│   │   ├── agent_tools.py    # Registers all role tools for the ADK agent
│   │   ├── supervisor.py     # OPL load, problem resolution, finish
│   │   ├── generator.py      # Logic map, generate_code, save zip
│   │   └── critic.py         # Evaluation metrics & scoring
│   ├── tool_helpers/
│   │   ├── coverage_graph.py # OPL/code graph canonicalization & similarity
│   │   ├── execution_readiness.py  # Static fullstack zip checks
│   │   ├── js_syntax.py      # JS/JSX parsing via esprima2
│   │   └── create_folder_dir.py    # Generator prompts & graph schema
│   ├── examples/             # Demo logic maps & evaluation payloads
│   └── opl_examples/         # Sample OPL specifications
└── services/
    ├── progress_tracker.py   # SSE activity log from agent events
    ├── zip_cache.py          # Short-lived in-memory zip storage
    └── maps.py               # Progress step labels & weights
```

> **Note:** `agent/tools.py` and `agent/agent_tools/` are legacy copies kept during the tools split; the live agent uses `agent/tools/agent_tools.py`.

## Setup

### 1. Install dependencies

```bash
cd appserver
pip install -r requirements.txt
```

Python **3.11+** recommended (matches local development and ADK).

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
| `GEMINI_MODEL` | No | Model id (default: `gemini-2.5-pro`) |
| `GEMINI_APP_NAME` | No | ADK app name (default: `model_based_codegen`) |
| `PORT` | No | Listen port (default: `5000`) |
| `FLASK_DEBUG` | No | Flask debug mode (default: `false`) |

Agent debug mode is configured in `config.py` (`server.agent_debug`: `0` = none, `1` = supervisor, `2` = generator, `3` = critic, `4` = all). Lower values return demo payloads from some tools instead of calling Gemini.

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

1. **Supervisor** loads the OPL, routes hand-offs, and resolves failures via `generate_problem`
2. **Generator** builds an OPL logic map, sets a project name, and calls `generate_code` to produce a base64-encoded zip (`frontend/` + `backend/`) plus a `code_coverage_graph`
3. **Critic** calls `get_evaluation_metrics` and `generate_code_evaluation`, then hands control back to the Supervisor
4. **Supervisor** finishes when the Critic’s `overall_score` meets the threshold (**70**), or retries via problem resolution

Progress is tracked by `GenerationProgressTracker`, which maps ADK tool calls to UI steps defined in `services/maps.py`.

### Critic evaluation

`generate_code_evaluation` combines two weighted metrics (default 50/50):

| Metric | What it checks |
|--------|----------------|
| **Graph coverage** | Similarity between an OPL reference graph (Gemini-extracted from OPL + logic map) and the Generator’s `code_coverage_graph` — entities, states, relations |
| **Syntax & executable** | Python (`ast`), JSON (`json.loads`), JS/JSX (**esprima2**), plus static execution-readiness checks (required files, Flask/React/Vite layout, API wiring) |

Scores are stored in session (`code_evaluation`) and persisted to MongoDB on the OPL document (`overall_score`, `graph_coverage_score`, `syntax_score`, `exec_score`).

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

The generated `backend/requirements.txt` is for the **downloaded project**, not this appserver’s dependencies.

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

- Agent OPL examples: `agent/opl_examples/`
- Training context files: `agent/train/`
- Evaluation and logic-map examples: `agent/examples/`
- Console output uses structured messages from `messages.py` (`SUCCESS`, `ERROR`, `NOTE`, etc.)
- Critic JS/JSX checks: `agent/tool_helpers/js_syntax.py` (requires `esprima2`; falls back to bracket balancing if unavailable)

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Agent is not loaded` on `/agent/` | Missing/invalid `GEMINI_API_KEY` or ADK import error |
| `Database not configured` on `/file/` | `MONGO_URL` not set or MongoDB unreachable |
| Download returns 404 | Zip expired (15 min TTL) or wrong `user_id` |
| Generation retries 3 times | Agent session missing `generated_code_zip` — check Gemini quota and agent logs |
| Port keeps incrementing | Another process is using the configured `PORT` |
| JS syntax always passes/fails oddly | Confirm `esprima2` is installed (`pip show esprima2`) |
