from __future__ import annotations
import base64
import io
import json
import re
import zipfile
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from agent.memory import DBconnection
from agent.examples.logic_map_example import logic_map_example
from messages import start_message, error_message, success_message
from extensions import call_gemini
from agent.tool_helpers.create_folder_dir import (
    frontend_skeleton,
    backend_skeleton,
    generate_project_prompt,
)
from agent.tool_helpers.coverage_graph import (
    canonicalize_coverage_graph,
    coerce_coverage_graph,
)

from config import CONFIG

# Get the agent debug type
AGENT_DEBUG = CONFIG["server"]["agent_debug"]

def _project_zip_dir_names(entry_paths: list[str]) -> list[str]:
    dirs: set[str] = set()
    for entry in entry_paths:
        parts = entry.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]) + "/")
    return sorted(dirs)

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

def _ensure_frontend_initialization(files: dict[str, str], project_slug: str) -> None:
    """
    Ensure the frontend is initialized

    Parameters:
        - files : The files map to ensure the frontend is initialized
        - project_slug : The slug of the project

    Returns:
        - None
    """
    # Get the package.json file
    pkg_raw = files.get("package.json")

    if pkg_raw:
        try:
            # Load the package.json file
            pkg = json.loads(pkg_raw)

            # Set the scripts
            scripts = pkg.setdefault("scripts", {})

            # Set the dev script
            scripts.setdefault("dev", "vite")

            # Set the predev script
            scripts["predev"] = "npm install"

            # Set the dependencies
            deps = pkg.setdefault("dependencies", {})
            deps.setdefault("axios", "^1.7.0")

            # Set the name
            pkg["name"] = project_slug

            # Set the package.json file
            files["package.json"] = json.dumps(pkg, indent=2) + "\n"
        except json.JSONDecodeError as exc:
            error_message("Tools", f"Failed to initialize frontend: {exc}")

def _ensure_backend_initialization(files: dict[str, str]) -> None:
    """
    Ensure the backend is initialized

    Parameters:
        - files : The files map to ensure the backend is initialized

    Returns:
        - None
    """
    # Get the requirements.txt file
    req = files.get("requirements.txt", "")

    # Add the required packages to the requirements.txt file
    for package in ("flask", "flask-cors"):
        if package not in req.lower():
            req = req.rstrip() + ("\n" if req and not req.endswith("\n") else "") + f"{package}\n"
    files["requirements.txt"] = req

    # Get the app.py file
    content = files.get("app.py", "")
    if not content:
        return
    if "flask_cors" not in content and "CORS(app)" not in content:
        # Check if the app.py file contains the flask import and CORS import
        if "from flask import" in content:
            content = content.replace(
                "from flask import",
                "from flask_cors import CORS\nfrom flask import",
                1,
            )
        elif "import flask" not in content.lower():
            content = "from flask_cors import CORS\n" + content

        # Check if the app.py file contains the app = Flask(__name__) and CORS(app)
        if "app = Flask(__name__)" in content and "CORS(app)" not in content:
            content = content.replace(
                "app = Flask(__name__)",
                "app = Flask(__name__)\nCORS(app)",
                1,
            )

    # Check if the app.py file contains the _install_dependencies function
    if "_install_dependencies()" not in content and '__name__ == "__main__"' in content:
        content = content.replace(
            'if __name__ == "__main__":',
            'if __name__ == "__main__":\n    _install_dependencies()',
            1,
        )

    # Set the app.py file
    files["app.py"] = content

def _normalize_files_map(files: dict[str, Any], part: str) -> dict[str, str]:
    """
    Normalize the files map

    Parameters:
        - files : The files map to normalize
        - part : The part of the files map to normalize

    Returns:
        - dict[str, str] : The normalized files map
    """

    normalized: dict[str, str] = {}
    for path, content in files.items():
        # Normalize the path
        clean = _normalize_project_path(path, part)

        if clean:
            # Add the normalized path to the files map
            normalized[clean] = content

    return normalized

def _normalize_project_path(path: str, part: str) -> str:
    """
    Normalize the project path

    Parameters:
        - path : The path to normalize
        - part : The part of the path to normalize

    Returns:
        - str : The normalized path
    """
    # Normalize the path
    clean = path.replace("\\", "/").lstrip("/")

    # Get the prefix
    prefix = f"{part}/"

    # Remove the prefix from the path
    while clean.startswith(prefix):
        clean = clean[len(prefix) :]

    return clean

def _parse_generated_project(raw: str) -> dict[str, Any]:
    """
    Parse the generated project

    Parameters:
        - raw : The raw text to parse

    Returns:
        - dict[str, Any] : The parsed project
    """
    # Strip the code fences from the raw text
    text = _strip_code_fences(raw)

    # Parse the JSON
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid JSON for project: {exc}"}

    # Check if the payload is a dictionary
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Gemini must return a JSON object"}

    # Get the frontend and backend files
    try:
        frontend_files = payload.get("frontend").get("files")
        backend_files = payload.get("backend").get("files")
    except Exception as exc:
        return {"status": "error", "message": f"Invalid payload for project: {exc}"}
        
    # Check if the frontend and backend files are valid
    if not isinstance(frontend_files, dict) or not frontend_files:
        return {"status": "error", "message": "missing or empty frontend.files"}
    if not isinstance(backend_files, dict) or not backend_files:
        return {"status": "error", "message": "missing or empty backend.files"}

    # Normalize the frontend and backend files
    frontend_files = _normalize_files_map(frontend_files, "frontend")
    backend_files = _normalize_files_map(backend_files, "backend")

    # Check if the frontend and backend files are valid
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

    raw_coverage_graph = coerce_coverage_graph(payload.get("code_coverage_graph")) or coerce_coverage_graph(
        payload
    )
    if raw_coverage_graph is None:
        raw_coverage_graph = {"nodes": []}
    code_coverage_graph = canonicalize_coverage_graph(raw_coverage_graph)

    return {
        "status": "success",
        "frontend_files": frontend_files,
        "backend_files": backend_files,
        "code_coverage_graph": code_coverage_graph,
    }

def _strip_code_fences(text: str) -> str:
    """
    Strip the code fences from the text

    Parameters:
        - text : The text to strip the code fences from

    Returns:
        - str : The text with the code fences stripped
    """
    text = text.strip()
    match = re.match(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _print_project_files_debug(frontend_files: dict[str, str], backend_files: dict[str, str]) -> None:
    """
    Print all generated frontend/backend paths

    Parameters:
        - frontend_files : The frontend files
        - backend_files : The backend files

    Returns:
        - None
    """
    for label, files in ("frontend", frontend_files), ("backend", backend_files):
        print(f"\n{'=' * 60}\n{label.upper()} ({len(files)} files)\n{'=' * 60}")
        for path in sorted(files):
            print(f"  {label}/{path} ({len(files[path])} chars)")
    print()

def _build_project_folders(
    opl_logic_map: dict[str, Any],
    opl: str,
    project_name: str,
    project_slug: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    """
    Build the project folders

    Parameters:
        - opl_logic_map : The OPL logic map
        - opl : The OPL specification
        - project_name : The name of the project
        - project_slug : The slug of the project

    Returns:
        - tuple[dict[str, str], dict[str, str], dict[str, Any]] : frontend, backend, coverage graph
    """
    # Build the frontend and backend files
    frontend_files = frontend_skeleton(project_name, project_slug)
    backend_files = backend_skeleton(project_name, project_slug)
    code_coverage_graph: dict[str, Any] = {"nodes": []}

    # Generate the project prompt
    prompt = generate_project_prompt(opl_logic_map, opl, project_name, project_slug)

    # Call the Gemini API to generate the project
    result = call_gemini(prompt)
    if result.get("status") == "success":
        # Parse the generated project
        parsed = _parse_generated_project(result["data"])

        if parsed.get("status") == "success":
            # Merge the frontend files
            frontend_files = dict(frontend_files)
            frontend_files.update(parsed["frontend_files"])

            # Merge the backend files
            backend_files = dict(backend_files)
            backend_files.update(parsed["backend_files"])
            code_coverage_graph = parsed.get("code_coverage_graph", {"nodes": []})
        else:
            error_message("GeneratorTools", parsed.get("message", "invalid Gemini project JSON"),)
    else:
        error_message("GeneratorTools", result.get("message", "project generation failed"))

    _ensure_frontend_initialization(frontend_files, project_slug)
    _ensure_backend_initialization(backend_files)
    return frontend_files, backend_files, code_coverage_graph

def is_valid_project_zip(zip_bytes: bytes) -> bool:
    """
    Check if the project zip is valid

    Parameters:
        - zip_bytes : The zip bytes

    Returns:
        - bool : True if the project zip is valid, False otherwise
    """

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return False

    # Check if the zip contains frontend and backend folders (no single files)
    if "frontend" in names or "backend" in names:
        return False

    frontend_files = [ n for n in names if n.startswith("frontend/") and not n.endswith("/") ]
    backend_files = [ n for n in names if n.startswith("backend/") and not n.endswith("/")]

    # Check if files aren't empty
    return len(frontend_files) >= 1 and len(backend_files) >= 1

def _sanitize_project_slug(name: str) -> str:
    """
    Sanitize the project slug

    Parameters:
        - name : The project name

    Returns:
        - str : The sanitized project slug
    """

    # Sanitize the project slug
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64] or "opl-project"

def _resolve_project_name(
    project_name: str | None,
    tool_context: ToolContext | None = None,
) -> tuple[str, str]:
    display = (project_name or "").strip()
    if not display and tool_context is not None:
        display = (tool_context.state.get("project_name") or "").strip()
    if not display:
        display = "OPL Project"
    return display, _sanitize_project_slug(display)

class GeneratorTools:
    """
        Generator Tools

        Includes:
            - get_opl_logic_map : Load or build the OPL logic map for code generation.
            - set_project_name : Store a human-readable project name chosen from the OPL specification.
            - generate_code : Build fullstack frontend/ (React+Vite+service.js) and backend/ (Flask+CORS) from OPL, zip them.
            - save_generated_code : Persist the session zip from generate_code to the database.
    """

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_logic_map(self) -> dict[str, Any]:
        """
            Load  OPL logic map from the database

            Parameters:
                - None

            Returns:
                - dict[str, Any] : The OPL logic map
        """
        start_message("GeneratorTools", "Get OPL logic map")

        if AGENT_DEBUG != 2 and AGENT_DEBUG != 4:
            success_message("GeneratorTools", "Returning demo OPL logic map")
            return logic_map_example

        # Get the latest OPL logic map from the database
        response = self._db.get_latest_opl_logic_map()
        if response.get("status") == "success":
            opl_logic_map = response.get("data").get("opl_logic_map")
            created_at = response.get("data").get("created_at")

            success_message("GeneratorTools", "Fetched OPL logic map from database at " + str(created_at))
            return opl_logic_map
        else:
            error_message("GeneratorTools", response.get("message"))
            return None

    def set_project_name(self, project_name: str, tool_context: ToolContext) -> dict[str, Any]:
        """
            Store generated project name chosen from the OPL specification

            Parameters:
                - project_name : The generated project name
                - tool_context : The tool context

            Returns:
                - dict[str, Any] : The result
        """
        start_message("GeneratorTools", "Set project name to " + project_name)

        display, slug = _resolve_project_name(project_name)
        tool_context.state["project_name"] = display
        tool_context.state["project_slug"] = slug

        success_message("GeneratorTools", "Successfully set project name to " + project_name)
        return {"status": "success", "message": "Successfully set project name to " + project_name}

    def generate_code(self,opl_logic_map: dict[str, Any],opl: str,tool_context: ToolContext,project_name: str | None = None,) -> dict[str, Any]:
        """
        Build fullstack frontend/ (React+Vite+service.js) and backend/ (Flask+CORS) from OPL, zip them.

        Parameters:
            - opl_logic_map : The OPL logic map
            - opl : The OPL specification
            - tool_context : The tool context
            - project_name : The project name

        Returns:
            - dict[str, Any] : The result
        """
        # Keep the project name stable across re-generations. Once a name was chosen
        # for this run (e.g. on the first Generator pass), a redo after a problem must
        # reuse it exactly instead of renaming it (e.g. appending "_v2").
        existing_name = (tool_context.state.get("project_name") or "").strip()
        if existing_name:
            display, slug = _resolve_project_name(existing_name)
        else:
            display, slug = _resolve_project_name(project_name, tool_context)
        start_message("GeneratorTools", "Generate project code for " + display)

        # Set the project name and slug in the tool context
        tool_context.state["project_name"] = display
        tool_context.state["project_slug"] = slug

        # Build the project folders
        frontend_files, backend_files, code_coverage_graph = _build_project_folders(
            opl_logic_map, opl, display, slug
        )
        _print_project_files_debug(frontend_files, backend_files)

        # Check if the frontend and backend files are valid
        if not frontend_files or not backend_files:
            error_message("GeneratorTools", "Failed to build project folders")
            return {"status": "error", "message": "Failed to build project folders"}

        # Zip the project folders
        zip_bytes = _zip_project_folders(frontend_files, backend_files)
        code_zip_base64 = base64.b64encode(zip_bytes).decode("ascii")

        # Set the generated code zip in the tool context
        tool_context.state["generated_code_zip"] = code_zip_base64
        tool_context.state["code_coverage_graph"] = code_coverage_graph

        # Record that the Generator completed so the Supervisor can route to the Critic.
        tool_context.state["last_completed_role"] = "generator"

        success_message(
            "GeneratorTools",
            "Generated project " + display + " with zip length " + str(len(zip_bytes)),
        )
        return {
            "status": "success",
            "message": "Project "
            + display
            + " generated successfully with zip length "
            + str(len(zip_bytes)),
        }

    def save_generated_code(self, tool_context: ToolContext) -> dict[str, Any]:
        """
            Persist the zip from ``generate_code`` to MongoDB.

            Reads ``generated_code_zip`` and ``opl_id`` from session; do not pass zip text as arguments.
        """
        start_message("GeneratorTools", "Save generated code to the database")

        if AGENT_DEBUG != 3 and AGENT_DEBUG != 4:
            success_message("GeneratorTools", "Debug mode is enabled, skipping save generated code")
            return {"status": "success", "message": "Zip saved to database"}

        zip_b64 = tool_context.state.get("generated_code_zip")
        if not zip_b64:
            error_message("GeneratorTools", "No generated code zip in session")
            return {
                "status": "error",
                "message": "No generated code zip in session. Run generate_code first.",
            }

        opl_id = (tool_context.state.get("opl_id") or "").strip()
        if not opl_id:
            error_message("GeneratorTools", "No opl_id in session")
            return {"status": "error", "message": "No opl_id in session"}

        try:
            zip_bytes = base64.b64decode(zip_b64)
        except Exception:
            error_message("GeneratorTools", "Failed to decode generated code zip from session")
            return {"status": "error", "message": "Failed to decode generated code zip from session"}

        if not is_valid_project_zip(zip_bytes):
            error_message("GeneratorTools", "Invalid project zip in session")
            return {"status": "error", "message": "Invalid project zip in session"}

        response = self._db.save_code_zip(zip_bytes, opl_id)
        if response.get("status") == "success":
            success_message("GeneratorTools", "Zip saved to database")
            return {"status": "success", "message": "Zip saved to database"}
        else:
            error_message("GeneratorTools", response.get("message"))
            return {"status": "error", "message": response.get("message")}

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_opl_logic_map,
            self.set_project_name,
            self.generate_code,
            self.save_generated_code,
        ]