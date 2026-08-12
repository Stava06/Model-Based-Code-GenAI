# MOSAIC

**Model-driven, OPM-based System with Agentic Iterative Code generation** — a full-stack app that turns **OPL (Object-Process Language)** specifications into runnable **React + Vite** frontends and **Flask** backends using a multi-role Gemini agent pipeline.

Upload an OPL file in the web UI, run generation, download a zip of the produced project, and review automated evaluation scores (graph coverage, syntax, executability).

This folder is the Capstone B implementation. For project-wide context, see the [repository README](../../README.md). Guides, poster, and demo live one level up in [`Capstone_B/`](../).

## Architecture

```
┌─────────────────┐     REST / SSE      ┌──────────────────┐
│  myapp/my-web   │ ◄─────────────────► │    appserver     │
│  React + Vite   │                     │  Flask + ADK     │
└─────────────────┘                     └────────┬─────────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    ▼            ▼            ▼
                              MongoDB      Gemini API    In-memory
                              (users,      (google-genai) zip cache
                               OPL, eval)
```

### Agent workflow

A single Google ADK agent orchestrates three logical roles:

| Role | Responsibility |
|------|----------------|
| **Supervisor** | Loads the OPL, coordinates hand-offs, retries on failure |
| **Generator** | Builds an OPL logic map, names the project, generates frontend/backend code into a zip |
| **Critic** | Evaluates generated code (graph coverage, syntax, execution readiness) and reports scores |

Generation progress is streamed to the client over **Server-Sent Events (SSE)**. When complete, the zip is cached server-side and downloaded via a follow-up request.

## Layout

| Path | Description |
|------|-------------|
| [`appserver/`](appserver/) | Flask API, agent pipeline, MongoDB integration |
| [`myapp/my-web/`](myapp/my-web/) | React client (login, upload, generate, profile) |
| [`appserver/agent/`](appserver/agent/) | ADK agent, tools, roles, OPL examples |
| [`appserver/api/`](appserver/api/) | REST blueprints: users, files, agent |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the web client)
- **MongoDB** (local or Atlas)
- **Google Gemini API key** ([Google AI Studio](https://aistudio.google.com/apikey))

## Quick start

### 1. Configure the server

```bash
cd appserver
pip install -r requirements.txt
```

Create `appserver/.env`:

```env
MONGO_URL=mongodb://localhost:27017
MONGO_DB=model_based_codegen
MONGO_USER_COLLECTION=users
MONGO_OPL_COLLECTION=opls
MONGO_OPL_LOGIC_MAP_COLLECTION=opl_logic_maps

GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-pro
GEMINI_APP_NAME=model_based_codegen

PORT=5000
FLASK_DEBUG=false
```

Start the API:

```bash
python app.py
```

The server prints the port it binds to (defaults to `5000`, auto-increments if busy).

### 2. Configure and run the client

```bash
cd myapp/my-web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The client talks to `http://localhost:5000` by default. Override with a `.env` file in `myapp/my-web`:

```env
VITE_SERVER_URL=http://localhost:5000
```

### 3. Use the app

1. **Register / log in** at `/login`
2. **New Project** — upload a `.txt` or `.html` OPL file
3. **Generate** — watch live agent progress, then download the zip and view evaluation metrics
4. **Profile / My Projects** — review saved projects

## End-to-end generation flow

1. Client saves the OPL via `POST /file/save`
2. Client opens `GET /agent/generate` (SSE) with `opl_id`, `user_id`, and `filename`
3. Server runs the agent, streaming progress events (`building_logic_map`, `generating`, `evaluating`, `packaging`, …)
4. Server emits a final `done` event with a `download_id`
5. Client fetches `GET /agent/generate/download` and triggers a browser download
6. Client loads evaluation scores from `GET /file/evaluation/<opl_id>`

## API overview

| Service | Base path | Purpose |
|---------|-----------|---------|
| Users | `/users` | Register, login, profile |
| Files | `/file` | Save OPL, fetch evaluation |
| Agent | `/agent` | Health check, SSE generation, zip download |

See [appserver/README.md](appserver/README.md) for full endpoint documentation.

## Health checks

```bash
curl http://localhost:5000/
curl http://localhost:5000/agent/
curl http://localhost:5000/file/
```

## Production notes

- Run the Flask app with **gunicorn** (included in `requirements.txt`) instead of `python app.py`
- Build the client with `npm run build` and serve the `dist/` folder behind a static host or reverse proxy
- Set `VITE_SERVER_URL` to your deployed API URL before building
- Generated zips are stored in an **in-memory cache** (15-minute TTL); use a shared store if you scale to multiple workers

## Capstone B materials

| Resource | Location |
|----------|----------|
| User Guide | [`../User Guide - MOSAIC.docx`](../User%20Guide%20-%20MOSAIC.docx) |
| Maintenance Guide | [`../Maintenance Guide - MOSAIC.docx`](../Maintenance%20Guide%20-%20MOSAIC.docx) |
| Book | [`../The Model Is the System - Book.docx`](../The%20Model%20Is%20the%20System%20-%20Book.docx) |
| Poster | [`../MOSAIC_poster.jpeg`](../MOSAIC_poster.jpeg) |
| Demonstration | [`../MOSAIC_demonstration.mkv`](../MOSAIC_demonstration.mkv) |

## Further reading

- [appserver/README.md](appserver/README.md) — server setup, API, agent internals
- [myapp/my-web/README.md](myapp/my-web/README.md) — client setup, routes, environment
- [Repository README](../../README.md) — Capstone A & B overview
