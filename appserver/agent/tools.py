"""
    ADK tool groups: Supervisor, Generator, Critic.
"""
from __future__ import annotations
import base64
import io
import json
import re
import zipfile
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from config import CONFIG
from .memory import DBconnection
from .opl_examples import demo1, demo2
from agent.examples.logic_map_example import logic_map_example
from agent.examples.eval_metrics_example import metrics_example
from agent.examples.eval_example import evaluation_example
from messages import start_message, error_message, success_message


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _gemini_api_keys() -> list[str]:
    gemini = CONFIG["gemini"]
    keys = list(gemini.get("api_keys") or [])
    primary = gemini.get("api_key")
    if primary and primary not in keys:
        keys.insert(0, primary)
    return keys


def _codegen_project_prompt(opl_logic_map: dict[str, Any], opl: str) -> str:
    return f"""Build a minimal, executable **fullstack website** from the OPL specification.
The React frontend and Flask backend must be wired together: UI actions call the backend over HTTP.

## OPL logic map (JSON)
{json.dumps(opl_logic_map, indent=2)}

## OPL specification
{opl.strip()}

## Fullstack integration (mandatory)
- Frontend runs on Vite (default port 5173); backend runs on Flask (port 5000).
- Every data mutation or read in the UI goes through `src/service.js` using **axios** — never call
  `fetch` or axios directly from React components.
- `src/service.js` exports async functions (one per backend operation) that use axios against
  `const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000"`.
- Backend routes must match the paths and HTTP methods used in `service.js` (prefer `/api/...` prefixes).
- Enable **CORS** on the Flask app so the Vite dev server can call the API cross-origin.
- React components import from `./service.js` and use its functions in `useEffect`, event handlers, etc.
- The generated app must work when the user runs backend first, then frontend.

## frontend (mandatory stack)
- **React + Vite** project (not plain HTML or Python).
- Runnable with: `cd frontend && npm run dev` (`predev` must run `npm install` first).
- Required files: `README.md`, `package.json`, `index.html`, `vite.config.js`,
  `src/main.jsx`, `src/App.jsx`, **`src/service.js`**.
- `package.json` must list **`axios`** in `dependencies`.
- Optional but recommended: `.env` with `VITE_API_URL=http://localhost:5000`.
- Reflect OPL objects/processes in the React UI; load and submit data via `service.js`.

## backend (mandatory stack)
- **Python Flask** project (not Node or plain scripts).
- Runnable with: `cd backend && python app.py` (must pip install from `requirements.txt` first).
- Required files: `README.md`, `app.py`, `requirements.txt` (include **`flask`** and **`flask-cors`**).
- `app.py` must: import `CORS` from `flask_cors`, create `app = Flask(__name__)`, call `CORS(app)`
  immediately after app creation, define JSON API routes matching `service.js`, and call
  `_install_dependencies()` before `app.run(host="0.0.0.0", port=5000, debug=True)` in `__main__`.
- Expose REST routes reflecting OPL objects/processes (GET list/detail, POST create, etc. as needed).

Return **only** JSON (no markdown):
{{
  "frontend": {{
    "files": {{
      "relative/path": "file contents",
      "README.md": "..."
    }}
  }},
  "backend": {{
    "files": {{
      "relative/path": "file contents",
      "README.md": "..."
    }}
  }}
}}

Paths in each `files` map are relative to that folder (do not prefix keys with `frontend/` or `backend/`).
Include every file needed to run the fullstack app (both projects connected via axios + CORS).
"""


FRONTEND_README = """# Frontend (React + Vite)

Fullstack app — start the **backend** first (port 5000), then this frontend.

```bash
cd frontend
npm run dev
```

`npm run dev` runs `npm install` first (via `predev`), then starts Vite on port 5173.
API calls go through `src/service.js` (axios) to `VITE_API_URL` or `http://localhost:5000`.
"""

BACKEND_README = """# Backend (Flask)

Fullstack app — start this server **before** the frontend.

```bash
cd backend
python app.py
```

`app.py` installs dependencies from `requirements.txt`, enables CORS, then starts Flask on port 5000.
"""

_BACKEND_INSTALL_HELPER = '''
import subprocess
import sys
from pathlib import Path


def _install_dependencies() -> None:
    req = Path(__file__).resolve().parent / "requirements.txt"
    if req.is_file():
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)]
        )
'''


def _minimal_frontend_scaffold() -> dict[str, str]:
    return {
        "package.json": json.dumps(
            {
                "name": "opl-frontend",
                "private": True,
                "type": "module",
                "scripts": {"predev": "npm install", "dev": "vite"},
                "dependencies": {
                    "axios": "^1.7.0",
                    "react": "^18.3.1",
                    "react-dom": "^18.3.1",
                },
                "devDependencies": {
                    "@vitejs/plugin-react": "^4.3.4",
                    "vite": "^6.0.0",
                },
            },
            indent=2,
        )
        + "\n",
        "index.html": """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OPL Frontend</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
        "vite.config.js": """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
""",
        "src/main.jsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
        "src/service.js": """import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export async function fetchStatus() {
  const response = await axios.get(`${API_URL}/api/status`)
  return response.data
}
""",
        "src/App.jsx": """import { useEffect, useState } from 'react'
import { fetchStatus } from './service.js'

export default function App() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchStatus()
      .then(setStatus)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '1rem' }}>
      <h1>OPL Frontend</h1>
      <p>Generated fullstack app — customize from OPL specification.</p>
      {error && <p style={{ color: 'crimson' }}>Backend: {error}</p>}
      {status && <pre>{JSON.stringify(status, null, 2)}</pre>}
    </main>
  )
}
""",
    }


def _minimal_backend_scaffold() -> dict[str, str]:
    return {
        "requirements.txt": "flask\nflask-cors\n",
        "app.py": '''from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.get("/")
def index():
    return jsonify({"service": "opl-backend", "message": "ok"})


@app.get("/api/status")
def api_status():
    return jsonify({"service": "opl-backend", "status": "ok"})


if __name__ == "__main__":
    _install_dependencies()
    app.run(host="0.0.0.0", port=5000, debug=True)
''',
    }


def _merge_files(base: dict[str, str], overlay: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    merged.update(overlay)
    return merged


def _ensure_frontend_bootstrap(files: dict[str, str]) -> None:
    files["README.md"] = FRONTEND_README
    pkg_raw = files.get("package.json")
    if pkg_raw:
        try:
            pkg = json.loads(pkg_raw)
            scripts = pkg.setdefault("scripts", {})
            scripts.setdefault("dev", "vite")
            scripts["predev"] = "npm install"
            deps = pkg.setdefault("dependencies", {})
            deps.setdefault("axios", "^1.7.0")
            files["package.json"] = json.dumps(pkg, indent=2) + "\n"
        except json.JSONDecodeError:
            pass
    files.setdefault(
        "src/service.js",
        """import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export async function fetchStatus() {
  const response = await axios.get(`${API_URL}/api/status`)
  return response.data
}
""",
    )


def _ensure_backend_bootstrap(files: dict[str, str]) -> None:
    files["README.md"] = BACKEND_README
    req = files.get("requirements.txt", "")
    for package in ("flask", "flask-cors"):
        if package not in req.lower():
            req = req.rstrip() + ("\n" if req and not req.endswith("\n") else "") + f"{package}\n"
    files["requirements.txt"] = req
    content = files.get("app.py", "")
    if not content:
        return
    if "flask_cors" not in content and "CORS(app)" not in content:
        if "from flask import" in content:
            content = content.replace(
                "from flask import",
                "from flask_cors import CORS\nfrom flask import",
                1,
            )
        elif "import flask" not in content.lower():
            content = "from flask_cors import CORS\n" + content
        if "app = Flask(__name__)" in content and "CORS(app)" not in content:
            content = content.replace(
                "app = Flask(__name__)",
                "app = Flask(__name__)\nCORS(app)",
                1,
            )
    if "_install_dependencies" not in content:
        lines = content.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_at = i + 1
        helper = _BACKEND_INSTALL_HELPER.strip().splitlines()
        for offset, helper_line in enumerate(helper):
            lines.insert(insert_at + offset, helper_line)
        content = "\n".join(lines)
    if "_install_dependencies()" not in content and '__name__ == "__main__"' in content:
        content = content.replace(
            'if __name__ == "__main__":',
            'if __name__ == "__main__":\n    _install_dependencies()',
            1,
        )
    files["app.py"] = content


def _normalize_project_path(path: str, part: str) -> str:
    clean = path.replace("\\", "/").lstrip("/")
    prefix = f"{part}/"
    while clean.startswith(prefix):
        clean = clean[len(prefix) :]
    return clean


def _project_zip_dir_names(entry_paths: list[str]) -> list[str]:
    dirs: set[str] = set()
    for entry in entry_paths:
        parts = entry.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]) + "/")
    return sorted(dirs)


def _is_valid_project_zip(zip_bytes: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return False

    # Reject legacy flat entries (single files named "frontend" / "backend").
    if "frontend" in names or "backend" in names:
        return False

    frontend_files = [
        n for n in names if n.startswith("frontend/") and not n.endswith("/")
    ]
    backend_files = [
        n for n in names if n.startswith("backend/") and not n.endswith("/")
    ]
    return len(frontend_files) >= 1 and len(backend_files) >= 1


def zip_entry_names(zip_bytes: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            return zf.namelist()
    except zipfile.BadZipFile:
        return []


def _normalize_files_map(files: dict[str, Any], part: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        clean = _normalize_project_path(path, part)
        if clean:
            normalized[clean] = content
    return normalized


def _files_from_part_section(section: Any, part: str) -> dict[str, str] | None:
    if not isinstance(section, dict):
        return None
    files = section.get("files", section)
    if not isinstance(files, dict) or not files:
        return None
    normalized = _normalize_files_map(files, part)
    return normalized or None


def _parse_generated_project(raw: str) -> dict[str, Any]:
    text = _strip_code_fences(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid JSON for project: {exc}"}

    if not isinstance(payload, dict):
        return {"status": "error", "message": "Gemini must return a JSON object"}

    frontend_files = _files_from_part_section(payload.get("frontend"), "frontend")
    backend_files = _files_from_part_section(payload.get("backend"), "backend")
    errors: list[str] = []
    if not frontend_files:
        errors.append("missing or empty frontend.files")
    if not backend_files:
        errors.append("missing or empty backend.files")
    if errors:
        return {
            "status": "error",
            "message": "Gemini must return frontend and backend file maps: "
            + "; ".join(errors),
        }

    return {
        "status": "success",
        "frontend_files": frontend_files,
        "backend_files": backend_files,
    }


def _zip_project_folders(
    frontend_files: dict[str, str],
    backend_files: dict[str, str],
) -> bytes:
    entries: dict[str, str] = {}
    for rel_path, content in frontend_files.items():
        rel = _normalize_project_path(rel_path, "frontend")
        if rel:
            entries[f"frontend/{rel}"] = content
    for rel_path, content in backend_files.items():
        rel = _normalize_project_path(rel_path, "backend")
        if rel:
            entries[f"backend/{rel}"] = content

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in _project_zip_dir_names(list(entries)):
            zf.writestr(dir_name, b"")
        for entry_path, content in sorted(entries.items()):
            zf.writestr(entry_path, content)
    return buf.getvalue()


def _call_gemini_for_project(
    opl_logic_map: dict[str, Any],
    opl: str,
) -> dict[str, Any]:
    api_keys = _gemini_api_keys()
    model = CONFIG["gemini"].get("model")

    if not api_keys:
        return {"status": "error", "message": "GEMINI_API_KEY is not configured"}

    try:
        from google import genai
    except ImportError:
        return {"status": "error", "message": "google-genai not installed"}

    errors: list[str] = []
    for api_key in api_keys:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=_codegen_project_prompt(opl_logic_map, opl),
                config={"temperature": 0.2, "response_mime_type": "application/json"},
            )
            raw = getattr(response, "text", None) or ""
            parsed = _parse_generated_project(raw)
            if parsed.get("status") == "success":
                return parsed
            errors.append(parsed.get("message", "Failed to parse project"))
        except Exception as exc:
            errors.append(str(exc))

    return {
        "status": "error",
        "message": errors[-1] if errors else "Gemini failed for project",
    }


def _build_project_folders(
    opl_logic_map: dict[str, Any],
    opl: str,
) -> tuple[dict[str, str], dict[str, str]]:
    frontend_scaffold = _minimal_frontend_scaffold()
    backend_scaffold = _minimal_backend_scaffold()
    result = _call_gemini_for_project(opl_logic_map, opl)
    if result.get("status") == "success":
        frontend_files = _merge_files(
            frontend_scaffold, result["frontend_files"]
        )
        backend_files = _merge_files(backend_scaffold, result["backend_files"])
    else:
        error_message(
            "GeneratorTools",
            result.get("message", "project generation failed"),
        )
        frontend_files = frontend_scaffold
        backend_files = backend_scaffold

    _ensure_frontend_bootstrap(frontend_files)
    _ensure_backend_bootstrap(backend_files)
    return frontend_files, backend_files


class SupervisorTools:
    """Supervisor — training intake, OPL intake, iteration routing, and finish."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_training_files(self) -> list[str]:
        """Load training OPL files (training mode, initial start)."""
        start_message("SupervisorTools", "get_training_files")

        # TODO: Get training files from MongoDB / local storage

        success_message("SupervisorTools", "get_training_files")
        return [demo1, demo2]

    def generate_opl_logic_map(self, opl_files: list[str]) -> dict[str, Any]:
        """Build an OPL logic map from training files (training mode)."""
        start_message("SupervisorTools", "generate_opl_logic_map")

        # TODO: Generate OPL logic map from training files

        success_message("SupervisorTools", "generate_opl_logic_map")
        return {"status": "success", "opl_logic_map": logic_map_example}

    def save_opl_logic_map(self, opl_logic_map: dict[str, Any]) -> dict[str, Any]:
        """Persist the OPL logic map to the database (training mode)."""
        start_message("SupervisorTools", "save_opl_logic_map")

        # TODO: Save OPL logic map to MongoDB

        success_message("SupervisorTools", "save_opl_logic_map")
        return {"status": "success", "message": "OPL logic map saved"}

    def get_opl_from_user(self, tool_context: ToolContext) -> str:
        """Resolve user-provided OPL (operational mode, initial start)."""
        start_message("SupervisorTools", "get_opl_from_user")

        opl = tool_context.state.get("opl")
        if opl:
            success_message("SupervisorTools", "get_opl_from_user")
            return opl

        # TODO: Get user OPL from MongoDB / local storage

        success_message("SupervisorTools", "get_opl_from_user")
        return demo1

    def generate_problem(
        self, message: str, tool_context: ToolContext
    ) -> dict[str, Any]:
        """Build the final delivery payload before finishing the run."""
        start_message("SupervisorTools", "generate_problem")

        code_zip_base64 = tool_context.state.get("generated_code_zip")
        result: dict[str, Any] = {"message": message}

        if code_zip_base64:
            try:
                zip_bytes = base64.b64decode(code_zip_base64)
            except Exception:
                zip_bytes = b""
            if _is_valid_project_zip(zip_bytes):
                result["status"] = "success"
                result["code_zip_base64"] = code_zip_base64
                tool_context.state["finish_code_zip_base64"] = code_zip_base64
            else:
                result["status"] = "failure"
                result["message"] = (
                    message or "Generated zip is missing frontend/ and backend/ folders"
                )
        else:
            result["status"] = "failure"
            if not message:
                result["message"] = "No generated code zip available"

        success_message("SupervisorTools", "generate_problem")
        return result

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to the database."""
        start_message("SupervisorTools", "save_problem")

        # TODO: Save problem to MongoDB

        success_message("SupervisorTools", "save_problem")
        return {
            "status": "success",
            "message": "Problem saved successfully",
        }

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_training_files,
            self.generate_opl_logic_map,
            self.save_opl_logic_map,
            self.get_opl_from_user,
            self.generate_problem,
            self.save_problem,
        ]


class GeneratorTools:
    """Generator — OPL load, code generation, and persistence."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_file(self, tool_context: ToolContext) -> str:
        """Resolve OPL file content from session state or storage."""
        start_message("GeneratorTools", "get_opl_file")

        opl = tool_context.state.get("opl")
        if opl:
            success_message("GeneratorTools", "get_opl_file")
            return opl

        # TODO: Get OPL from local storage / MongoDB

        success_message("GeneratorTools", "get_opl_file")
        return demo1

    def get_opl_logic_map(self, opl: str) -> dict[str, Any]:
        """Load or build the OPL logic map for code generation."""
        start_message("GeneratorTools", "get_opl_logic_map")

        # TODO: Retrieve or generate OPL logic map from OPL

        success_message("GeneratorTools", "get_opl_logic_map")
        return logic_map_example

    def generate_code(
        self,
        opl_logic_map: dict[str, Any],
        opl: str,
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """Build fullstack frontend/ (React+Vite+service.js) and backend/ (Flask+CORS) from OPL, zip them."""
        start_message("GeneratorTools", "generate_code")

        frontend_files, backend_files = _build_project_folders(opl_logic_map, opl)
        if not frontend_files or not backend_files:
            error_message("GeneratorTools", "generate_code")
            return {"status": "error", "message": "Failed to build project folders"}

        zip_bytes = _zip_project_folders(frontend_files, backend_files)
        code_zip_base64 = base64.b64encode(zip_bytes).decode("ascii")
        tool_context.state["generated_code_zip"] = code_zip_base64

        success_message("GeneratorTools", "generate_code")
        return {
            "status": "success",
            "message": "Project zip saved to session (frontend/ and backend/ folders).",
            "frontend_files": sorted(frontend_files.keys()),
            "backend_files": sorted(backend_files.keys()),
            "zip_entry_names": [
                *(f"frontend/{p}" for p in sorted(frontend_files)),
                *(f"backend/{p}" for p in sorted(backend_files)),
            ],
        }

    def save_generated_code(self, tool_context: ToolContext) -> dict[str, Any]:
        """Persist the session zip from generate_code to the database."""
        start_message("GeneratorTools", "save_generated_code")

        chosen = tool_context.state.get("generated_code_zip")
        if not chosen:
            error_message("GeneratorTools", "save_generated_code: no zip in session")
            return {
                "status": "error",
                "message": "Call generate_code first — no zip in session",
            }

        try:
            zip_bytes = base64.b64decode(chosen)
        except Exception:
            zip_bytes = b""
        if not _is_valid_project_zip(zip_bytes):
            error_message(
                "GeneratorTools",
                "save_generated_code: zip missing frontend/ and backend/ folders",
            )
            return {
                "status": "error",
                "message": "Zip must contain frontend/ and backend/ folder trees",
            }

        # TODO: Save generated code zip to MongoDB

        success_message("GeneratorTools", "save_generated_code")
        return {"status": "success", "message": "Generated code zip saved"}

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_opl_file,
            self.get_opl_logic_map,
            self.generate_code,
            self.save_generated_code,
        ]


class CriticTools:
    """Critic — OPL map review and code evaluation."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_logic_map_from_db(self) -> dict[str, Any]:
        """Load the OPL logic map from the database."""
        start_message("CriticTools", "get_opl_logic_map_from_db")

        # TODO: Get OPL logic map from MongoDB

        success_message("CriticTools", "get_opl_logic_map_from_db")
        return logic_map_example

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """Fetch metrics for code evaluation."""
        start_message("CriticTools", "get_evaluation_metrics")

        # TODO: Get evaluation metrics from MongoDB

        success_message("CriticTools", "get_evaluation_metrics")
        return metrics_example

    def generate_code_evaluation(
        self,
        code: str,
        metrics: list[dict[str, Any]],
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """Produce code-level evaluation results."""
        start_message("CriticTools", "generate_code_evaluation")

        # TODO: Eval with Judge0, graph coverage, code BLEU

        overall_eval = evaluation_example
        tool_context.state["code_evaluation"] = overall_eval

        success_message("CriticTools", "generate_code_evaluation")
        return {"status": "success", "evaluation": overall_eval}

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_opl_logic_map_from_db,
            self.get_evaluation_metrics,
            self.generate_code_evaluation,
        ]


class AgentTools:
    """All tools for the singular agent (unique names, no duplicates)."""

    def __init__(self, db: DBconnection | None = None):
        db = db or DBconnection.from_config()
        self._supervisor = SupervisorTools(db)
        self._generator = GeneratorTools(db)
        self._critic = CriticTools(db)

    def set_current_role(self, role: str, tool_context: ToolContext) -> dict[str, Any]:
        """Switch active role: supervisor, generator, or critic."""
        allowed = {"supervisor", "generator", "critic"}
        if role not in allowed:
            return {
                "status": "error",
                "message": f"role must be one of {sorted(allowed)}",
            }
        tool_context.state["current_role"] = role
        return {"status": "success", "current_role": role}

    def adk_tools(self) -> list[Callable[..., Any]]:
        by_name: dict[str, Callable[..., Any]] = {}

        def add(fn: Callable[..., Any]) -> None:
            by_name[fn.__name__] = fn

        for fn in self._supervisor.adk_tools():
            add(fn)
        for fn in self._generator.adk_tools():
            add(fn)
        for fn in self._critic.adk_tools():
            add(fn)

        return [self.set_current_role, *by_name.values()]


def get_project_zip_from_state(state: dict[str, Any]) -> str | None:
    """
    Return a base64 project zip from session state if present and valid.

    Does not re-run code generation; the agent must have produced the zip via
    ``generate_code`` (or ``finish_code_zip_base64`` from ``generate_problem``).
    """
    zip_b64 = state.get("finish_code_zip_base64") or state.get("generated_code_zip")
    if not zip_b64:
        return None
    try:
        if _is_valid_project_zip(base64.b64decode(zip_b64)):
            return zip_b64
    except Exception:
        pass
    return None
