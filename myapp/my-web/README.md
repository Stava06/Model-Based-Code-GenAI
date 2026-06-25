# Web Client

React single-page application for Model-Based Code GenAI. Users register, upload OPL specifications, trigger AI code generation, download the resulting project zip, and view evaluation metrics.

## Stack

- **React 19** + **Vite 8**
- **React Router 7** — client-side routing
- **Tailwind CSS 4** — styling
- **Axios** — REST calls (auth, file save, evaluation)
- **fetch** — SSE generation stream and zip download

## Project structure

```
myapp/my-web/
├── index.html
├── vite.config.js
├── package.json
├── public/
└── src/
    ├── main.jsx
    ├── App.jsx                 # Route definitions
    ├── index.css
    ├── services/
    │   └── UserService.js      # API client (REST + SSE)
    ├── utils/
    │   └── passwordHash.js     # Client-side password hashing
    └── components/
        ├── login/
        │   └── login.jsx
        ├── NavBar/
        │   └── NavBar.jsx
        └── homepage/
            ├── Homepage.jsx    # Shell with nav + view switcher
            ├── NewProject.jsx  # OPL upload & save
            ├── Generate.jsx    # SSE progress, download, metrics
            ├── Profile.jsx
            └── Information.jsx
```

## Setup

### 1. Install dependencies

```bash
cd myapp/my-web
npm install
```

### 2. Environment

The client reads the API base URL from `VITE_SERVER_URL`. If unset, it defaults to `http://localhost:5000`.

Create `.env` in this directory (optional):

```env
VITE_SERVER_URL=http://localhost:5000
```

> Set this to your deployed API URL **before** running `npm run build` for production.

### 3. Run

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

Make sure the [app server](../../appserver/README.md) is running first.

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/login` | `Login` | Register and sign in |
| `/newproject` | `NewProject` | Upload `.txt` or `.html` OPL file, save to server |
| `/generate` | `Generate` | Live generation progress, zip download, evaluation scores |
| `/profile` | `Profile` | User profile and saved projects |

`/generate` expects query parameters set by New Project after a successful save:

```
/generate?opl_id=<id>&user_id=<id>&filename=<name>.zip
```

## User flow

1. **Login / Register** — credentials are sent to `/users/login` and `/users/register` (password is hashed client-side before transmission)
2. **New Project** — user picks a `.txt` or `.html` file; HTML is stripped to plain text. The OPL is saved via `POST /file/save`
3. **Generate** — navigates to `/generate` with the returned `opl_id`
4. **Progress** — `streamGenerateProject` opens an SSE connection to `/agent/generate` and renders a live activity log (logic map, code generation, evaluation, packaging)
5. **Download** — on the `done` event, the client cancels the SSE reader, fetches the zip from `/agent/generate/download`, and triggers a browser download
6. **Metrics** — evaluation scores are loaded from `/file/evaluation/<opl_id>` and shown as circular progress charts (overall, graph coverage, syntax, executability)
7. **Congratulations** — next-step instructions for running the generated frontend and backend locally

## API integration (`UserService.js`)

| Function | Backend | Purpose |
|----------|---------|---------|
| `registerUser` | `POST /users/register` | Create account |
| `loginUser` | `GET /users/login` | Authenticate |
| `saveOplFile` | `POST /file/save` | Persist OPL text |
| `streamGenerateProject` | `GET /agent/generate` | SSE progress stream |
| `downloadGeneratedProject` | `GET /agent/generate/download` | Fetch zip blob |
| `getOplEvaluation` | `GET /file/evaluation/:id` | Load evaluation scores |

### SSE handling

The generation stream parser:

- Buffers and splits SSE `data:` frames on `\n\n`
- Stops reading as soon as a `done` event arrives and calls `reader.cancel()` to release the HTTP connection
- Invokes `onDone` only after the stream is closed/cancelled, then starts the zip download via a separate `fetch` request

This avoids a browser connection-pool deadlock between the open SSE connection and the download request.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (port 5173) |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview the production build |
| `npm run lint` | Run ESLint |

## Production build

```bash
VITE_SERVER_URL=https://api.your-domain.com npm run build
```

Serve the `dist/` folder with any static file host. Ensure the API allows CORS from your frontend origin (the server uses `flask-cors` with default permissive settings).

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Network errors on all requests | App server not running, or `VITE_SERVER_URL` points to wrong host/port |
| Generation stuck at 100% / no download | Hard-refresh the page; ensure server has latest `agent_api.py` (`Connection: close` on SSE) |
| "Missing generation parameters" | Navigated to `/generate` directly — start from New Project |
| Evaluation scores show "not available" | Critic evaluation may not have persisted yet; scores are saved during generation |
| Login fails | Check MongoDB is running and user exists |
