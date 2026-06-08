"""
  This module contains the skeleton for the frontend and backend of the project.

  Includes:
  - frontend_skeleton : The skeleton for the frontend of the project.
  - backend_skeleton : The skeleton for the backend of the project.
"""
import json
from typing import Any

def frontend_skeleton(project_name: str, project_slug: str) -> dict[str, str]:
  """
  Generate the skeleton for the frontend of the project

  Parameters:
    - project_name : The name of the project
    - project_slug : The slug of the project

  Returns:
    - dict[str, str] : The skeleton for the frontend of the project
  """

  return {
        "package.json": json.dumps(
            {
                "name": project_slug,
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
        "index.html": f"""<!DOCTYPE html>
                            <html lang="en">
                              <head>
                                <meta charset="UTF-8" />
                                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                                <title>{project_name}</title>
                              </head>

                              <body>
                                <div id="root"></div>
                                <script type="module" src="/src/main.jsx"></script>
                              </body>
                            </html>
                          """,
        "vite.config.js": """
          import { defineConfig } from 'vite'
          import react from '@vitejs/plugin-react'

          export default defineConfig({
          plugins: [react()],
          })
          """
    }


def backend_skeleton(project_name: str, project_slug: str) -> dict[str, str]:
  """
  Generate the skeleton for the backend of the project

  Parameters:
    - project_name : The name of the project
    - project_slug : The slug of the project

  Returns:
    - dict[str, str] : The skeleton for the backend of the project
  """

  return {
        "requirements.txt": "flask\nflask-cors\n"
    }

def coverage_graph_schema() -> str:
    """
    Generate the graph to JSON prompt

    Parameters:
        - None

    Returns:
        - str : The graph to JSON prompt
    """
    return (
            "{\n"
            '  "nodes": [\n'
            "    {\n"
            '      "name": "<ObjectOrProcessName>",\n'
            '      "type": "object" | "process",\n'
            '      "states": ["<state1>", "<state2>"],\n'
            '      "relations": [\n'
            "        {\n"
            '          "from": "<source node name>",\n'
            '          "to": "<target node name>",\n'
            '          "type": "<relation_type>",\n'
            '          "from_state": "<optional state on from>",\n'
            '          "to_state": "<optional state on to>"\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- One node per OPL object or process ONLY — never per state.\n"
            "- Put all states in the node's states[] array (e.g. WaterTank.states: "
            "[\"empty\", \"full\"]; CoffeeType.states: [\"espresso\", \"latte\"]).\n"
            "- type must be exactly \"object\" or \"process\".\n"
            "- Relation types use snake_case: agent_link, instrument_link, consumption_link, "
            "result_link, effect_link, procedural_link, aggregation_participation, "
            "exhibition_characterization.\n"
            "- Put each relation only on the from node's relations array (never on the to node).\n"
            "- from and to must match top-level node name values exactly.\n"
            "- Return only valid JSON.\n"
        )

def generate_project_prompt(opl_logic_map: dict[str, Any], opl: str, project_name: str, slug: str) -> str:
  """
  Generate the project prompt

  Parameters:
    - opl_logic_map : The OPL logic map
    - opl : The OPL specification
    - project_name : The name of the project
    - slug : The slug of the project
  """
  
  return f"""Build a runnable, domain-specific **fullstack website** from the OPL below.
Prioritize working React UI and Flask API over documentation. The app must reflect OPL objects
and processes — not a generic template. Starter scaffolding may exist; **replace** placeholder
UI/API with domain-specific implementations — do not return them unchanged.
While implementing code, record every OPL object/process you implement in the top-level
`code_coverage_graph` field (see Graph Section). **Do not** add a graph file inside
`frontend/` or `backend/` — the graph is metadata for evaluation only, not part of the zip.

The React frontend and Flask backend must be wired together: UI actions call the backend over HTTP.

## Project name (mandatory)
- Human-readable name: **{project_name}**
- npm package slug: `{slug}` (use in `package.json` `"name"`, HTML `<title>`, main heading, README titles)
- Name the app from the OPL domain (objects, processes, purpose) — not generic placeholders like "OPL Frontend".

## OPL logic map

### Objects
{opl_logic_map.get("objects", "")}
### Processes
{opl_logic_map.get("processes", "")}
### Relations
{opl_logic_map.get("relations", "")}

## OPL specification
{opl.strip()}

## Implementation depth (mandatory — code, not docs)
- **Do not** return placeholder UIs (e.g. only `<h1>Hello World</h1>`) or a backend with only `/`.
- `src/App.jsx`: real layout (sections or nav), data loaded in `useEffect` via `service.js`.
- `src/service.js`: one exported async function per backend route; paths must match `app.py`.
- `app.py`: matching `/api/...` routes; simple in-memory or JSON-file store (no external DB).
- You may add `src/components/*.jsx` or small backend helpers when it improves clarity.

## Boundaries (do not over-engineer)
- Stay faithful to the OPL domain and logic map. Creativity = clear UX and sensible API shapes,
  not features absent from the OPL.
- No auth, payments, Docker, or extra frameworks beyond React+Vite+axios and Flask+CORS.
- Keep standard entry/config files (`main.jsx`, `vite.config.js`, `requirements.txt`

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
- New files can be created in the frontend and backend folders when needed; list them in README briefly.

## frontend (mandatory stack)
- **React + Vite** project (not plain HTML or Python).
- Runnable with: `cd frontend && npm run dev` (`predev` must run `npm install` first).
- Required files: `README.md`, `package.json`, `index.html`, `vite.config.js`,
  `src/main.jsx`, `src/App.jsx`, **`src/service.js`**.
- `package.json` must list **`axios`** in `dependencies`.
- Optional but recommended: `.env` with `VITE_API_URL=http://localhost:5000`.

## backend (mandatory stack)
- **Python Flask** project (not Node or plain scripts).
- Runnable with: `cd backend && python app.py` (must pip install from `requirements.txt` first).
- Required files: `README.md`, `app.py`, `requirements.txt` (include **`flask`** and **`flask-cors`**).
- `app.py` must: import `CORS` from `flask_cors`, create `app = Flask(__name__)`, call `CORS(app)`
  immediately after app creation, define JSON API routes matching `service.js`, and call
  `_install_dependencies()` before `app.run(host="0.0.0.0", port=5000, debug=True)` in `__main__`.

## Graph Section (`code_coverage_graph`)
For each OPL object or process you implement in frontend/backend code, add a node to
`code_coverage_graph` with its states in `states[]` (not as separate nodes). For each
relation between implemented entities, add an entry on the source node's `relations` array.
Example: WaterTank has states [\"empty\", \"full\"] and a relation
{{\"from\": \"WaterTank\", \"to\": \"WaterTank\", \"to_state\": \"full\", \"type\": \"exhibition_characterization\"}}.
Use this structure and rules:
{coverage_graph_schema()}

## README (short)
- Each `README.md`: how to run, prerequisites, and one short paragraph mapping OPL objects/processes
  to UI/API. Do not spend most of the output on documentation.

## Output verification (before returning JSON)
- Every major object from the logic map appears in routes, `service.js`, or visible UI labels.
- You **must** include full contents for: `src/App.jsx`, `src/service.js`, `app.py` (every generation).

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
  }},
  "code_coverage_graph": {{
    "nodes": [
      {{
        "name": "<implemented entity>",
        "type": "object",
        "states": ["<state1>", "<state2>"],
        "relations": [
          {{
            "from": "<source>",
            "to": "<target>",
            "type": "<relation_type>",
            "from_state": "<optional>",
            "to_state": "<optional>"
          }}
        ]
      }}
    ]
  }}
}}
"""