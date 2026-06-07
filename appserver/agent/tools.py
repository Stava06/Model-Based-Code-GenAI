"""
    ADK tool groups: Supervisor, Generator, Critic.
"""
from __future__ import annotations
import ast
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from .memory import DBconnection
from .opl_examples import demo1, demo3
from agent.examples.logic_map_example import logic_map_example
from agent.examples.eval_metrics_example import metrics_example
from agent.examples.eval_example import evaluation_example
from messages import start_message, error_message, success_message
from extensions import call_gemini
from .agent_tools.create_folder_dir import (
    frontend_skeleton,
    backend_skeleton,
    generate_project_prompt,
    coverage_graph_schema,
)
from .agent_tools.coverage_graph import (
    canonicalize_coverage_graph,
    graph_similarity_score,
)
##############################################################################################################################################################
##############################################################################################################################################################
##############################################################################################################################################################

def _project_zip_dir_names(entry_paths: list[str]) -> list[str]:
    dirs: set[str] = set()
    for entry in entry_paths:
        parts = entry.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]) + "/")
    return sorted(dirs)

def zip_entry_names(zip_bytes: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            return zf.namelist()
    except zipfile.BadZipFile:
        return []

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

##############################################################################################################################################################
##############################################################################################################################################################
##############################################################################################################################################################

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

    raw_coverage_graph = payload.get("code_coverage_graph")
    if not isinstance(raw_coverage_graph, dict):
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

class SupervisorTools:
    """
        Supervisor Tools

        Includes:
            - get_opl : Resolve user-provided OPL (operational mode, initial start).
            - supervisor_first_step : Persist OPL and complete initial supervisor setup in session.
            - generate_problem : Record a workflow problem in session state (call before finish when something failed).
            - finish_and_return_user : Stage final delivery (code zip) and return the user message.
    """

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl(self, opl_id: str) -> str:
        """
            Resolve OPL

            Parameters:
                - opl_id : The ID of the OPL

            Returns:
                - str : OPL
        """
        start_message("SupervisorTools", f"Get OPL by id {opl_id}")

        if opl_id:
            response = self._db.get_opl(opl_id)

            if response.get("status") == "success":
                opl_retrieved = response.get("data")
                success_message("SupervisorTools", {"opl length": len(opl_retrieved) if opl_retrieved else 0})

                return opl_retrieved
            else:
                error_message("SupervisorTools", response.get("message"))
                return None
        else:
            #TODO: Get opl from Local Storage
            return demo1

    def supervisor_first_step(
        self, opl: str, tool_context: ToolContext, opl_id: str | None = None
    ) -> dict[str, Any]:
        """
            Complete supervisor initial start and hand off to the generator.

            Pass OPL text from ``get_opl``. Persists ``opl`` in session, sets
            ``cnt_itr`` to 0, ``initial_start`` to False, and ``current_role`` to ``generator``.
        """
        start_message("SupervisorTools", "supervisor_first_step")

        if not opl or not str(opl).strip():
            error_message("SupervisorTools", "supervisor_first_step: missing opl")
            return {
                "status": "error",
                "message": "opl is required (pass the string returned from get_opl)",
            }

        opl_text = str(opl)
        tool_context.state["opl"] = opl_text
        resolved_id = (opl_id or tool_context.state.get("opl_id") or "").strip()
        if resolved_id:
            tool_context.state["opl_id"] = resolved_id

        tool_context.state["cnt_itr"] = 0
        tool_context.state["initial_start"] = False
        tool_context.state["current_role"] = "generator"

        success_message(
            "SupervisorTools",
            {
                "opl length": len(opl_text),
                "initial_start": False,
                "cnt_itr": 0,
                "current_role": "generator",
            },
        )
        return {
            "status": "success",
            "message": (
                "Supervisor first step done; current_role is generator. "
                "Continue with the full generator workflow including generate_code."
            ),
            "opl_length": len(opl_text),
            "initial_start": False,
            "cnt_itr": 0,
            "current_role": "generator",
        }

    def generate_problem(self, message: str, tool_context: ToolContext) -> dict[str, Any]:
        """
            Record a workflow problem in session state

            Parameters:
                - message : The problem message

            Returns:
                - dict[str, Any] : The result
        """
        start_message("SupervisorTools", "Generate problem")

        tool_context.state["workflow_problem"] = message

        success_message("SupervisorTools", {"message": message})
        return {"status": "success", "message": message}

    def finish_and_return_user(self, tool_context: ToolContext) -> dict[str, Any]:
        """
            Stage final delivery (code zip) and return the user message

            Parameters:
                - tool_context : The tool context

            Returns:
                - dict[str, Any] : The result
        """
        start_message("SupervisorTools", "Finish and return user")

        problem = tool_context.state.get("workflow_problem", "")
        generated_code_zip = tool_context.state.get("generated_code_zip")
        result: dict[str, Any] = {"problem": problem or None}
        project_name = tool_context.state.get("project_name") or "Undifined Project Name"
        project_slug = tool_context.state.get("project_slug") or "undifined-project-slug"

        # Check if the generated code zip is available
        if generated_code_zip:
            try:
                zip_bytes = base64.b64decode(generated_code_zip)
            except Exception:
                zip_bytes = b""

            # Check if the zip is valid
            if is_valid_project_zip(zip_bytes):
                result["status"] = "success"
                result["generated_code_zip"] = generated_code_zip

                result["message"] = f"Generated fullstack code for '{project_name}' is ready for download."
            else:
                result["status"] = "failure"
                result["message"] = problem or "Generated zip is missing frontend/ and backend/ folders"
        else:
            result["status"] = "failure"
            result["message"] = problem or "No generated code zip available"

        # Add project name, slug, and download filename to the result
        result["project_name"] = project_name
        result["project_slug"] = project_slug
        result["download_filename"] = f"{project_slug}.zip"

        success_message("SupervisorTools", {"status": result["status"], "message": result["message"]})
        return result

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_opl,
            self.supervisor_first_step,
            self.generate_problem,
            self.finish_and_return_user,
        ]


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
        start_message("GeneratorTools", "Generate project code for " + project_name)

        display = project_name.strip() or "OPL Project"
        slug = _sanitize_project_slug(display)

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

        success_message("GeneratorTools", "Generated project " + project_name + " with zip length " + str(len(zip_bytes)))
        return {"status": "success", "message": "Project " + project_name + " generated successfully with zip length " + str(len(zip_bytes))}

    def save_generated_code(self, tool_context: ToolContext) -> dict[str, Any]:
        """
            Persist the zip from ``generate_code`` to MongoDB.

            Reads ``generated_code_zip`` and ``opl_id`` from session; do not pass zip text as arguments.
        """
        start_message("GeneratorTools", "Save generated code to the database")

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


class CriticTools:
    """
        Critic — OPL map review and code evaluation

        Includes:
            - get_opl_logic_map_from_db : Load the OPL logic map from the database
            - get_evaluation_metrics : Fetch metrics for code evaluation
            - generate_code_evaluation : Produce code-level evaluation results
    """

    def __init__(self, db: DBconnection):
        self._db = db

    def _extract_opl_reference_graph(self, opl_id: str) -> dict[str, Any] | None:
        logic_map_response = self._db.get_latest_opl_logic_map()
        if logic_map_response.get("status") != "success":
            error_message("CriticTools", logic_map_response.get("message", "Failed to load logic map"))
            return None

        opl_logic_map = logic_map_response.get("data", {}).get("opl_logic_map", {})

        opl_response = self._db.get_opl(opl_id)
        if opl_response.get("status") != "success":
            error_message("CriticTools", opl_response.get("message", f"Failed to load OPL: {opl_id}"))
            return None

        opl = opl_response.get("data", "")

        prompt = (
            "You are analyzing an OPL (Object-Process Language) specification.\n"
            "Extract every object and process from the OPL into a coverage graph.\n"
            "Put states in each node's states[] array — "
            "never as separate top-level nodes.\n\n"
            "Use this logic map to map each relation to the closest relation type "
            "(objects, processes, and relations sections):\n"
            f"{json.dumps(opl_logic_map, indent=2)}\n\n"
            "OPL specification:\n"
            f"{opl}\n\n"
            "Return only valid JSON with this schema:\n"
            f"{coverage_graph_schema()}"
        )

        result = call_gemini(prompt)
        if result.get("status") != "success":
            error_message("CriticTools", result.get("message", "Gemini graph extraction failed"))
            return None

        try:
            opl_coverage_graph = json.loads(_strip_code_fences(result.get("data", "")))
        except json.JSONDecodeError as exc:
            error_message("CriticTools", f"Invalid graph JSON from Gemini: {exc}")
            return None

        if not isinstance(opl_coverage_graph, dict) or not isinstance(opl_coverage_graph.get("nodes"), list):
            error_message("CriticTools", "Gemini response missing nodes array")
            return None

        return canonicalize_coverage_graph(opl_coverage_graph)

    def _get_opl_reference_graph(
        self, opl_id: str, tool_context: ToolContext | None = None
    ) -> dict[str, Any] | None:
        if tool_context is not None:
            cached = tool_context.state.get("opl_reference_graph")
            if isinstance(cached, dict) and isinstance(cached.get("nodes"), list):
                return cached

        opl_coverage_graph = self._extract_opl_reference_graph(opl_id)
        if opl_coverage_graph is None:
            return None

        if tool_context is not None:
            tool_context.state["opl_reference_graph"] = opl_coverage_graph
        return opl_coverage_graph

    def _graph_coverage_score(self,opl_id: str,code_coverage_graph: dict[str, Any] | None,tool_context: ToolContext | None = None,) -> dict[str, float]:
        graph_coverage_scores = {
            "entity_score": 0.0,
            "state_score": 0.0,
            "relation_score": 0.0,
            "overall_score": 0.0,
        }
        
        if not code_coverage_graph or not isinstance(code_coverage_graph, dict):
            error_message("CriticTools", "No code_coverage_graph in session state")
            return graph_coverage_scores

        opl_coverage_graph = self._get_opl_reference_graph(opl_id, tool_context)
        if opl_coverage_graph is None:
            return graph_coverage_scores

        graph_coverage_scores = graph_similarity_score(opl_coverage_graph, code_coverage_graph)
        success_message("CriticTools", {"graph_coverage": graph_coverage_scores})
        return graph_coverage_scores

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """
            Fetch metrics for code evaluation

            Parameters:
                - None

            Returns:
                - dict[str, Any] : The evaluation metrics
        """
        start_message("CriticTools", "Get evaluation metrics")

        # Evaluation metrics
        eval_metrics = {
            "graph_coverage":{ 
                "weight": 0.5, 
                "description": "The graph is fully covered, which means all the objects and processes of the given OPLare represented in the code"
                },
            "code_bleu":{ 
                "weight": 0.5, 
                "description": "Syntax-valid and executable generated code (parse + build smoke tests)"
                },
        }

        success_message("CriticTools", {"eval_metrics": eval_metrics})
        return eval_metrics

    def _syntax_and_executable_score(self, code: str) -> dict[str, float]:
        empty = {"syntax_score": 0.0, "executable_score": 0.0, "overall_score": 0.0}
        if not code or not str(code).strip():
            error_message("CriticTools", "No code provided for syntax/executable scoring")
            return empty

        syntax_results: list[bool] = []
        executable_results: list[bool] = []
        project_root: Path | None = None
        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        code_text = str(code).strip()

        def _check_python_syntax(source: str, label: str) -> None:
            try:
                ast.parse(source)
                syntax_results.append(True)
            except SyntaxError as exc:
                error_message("CriticTools", f"Python syntax error in {label}: {exc}")
                syntax_results.append(False)

        def _check_js_syntax(file_path: Path) -> None:
            if shutil.which("node") is None:
                error_message("CriticTools", f"Node.js not found; skipping JS syntax for {file_path.name}")
                syntax_results.append(False)
                return
            script = (
                "const parser=require('@babel/parser');"
                "const fs=require('fs');"
                "parser.parse(fs.readFileSync(process.argv[1],'utf8'),"
                "{sourceType:'module',plugins:['jsx']});"
            )
            babel_cmd = ["npx", "--yes", "-p", "@babel/parser", "node", "-e", script, str(file_path)]
            babel_kwargs: dict[str, Any] = {
                "capture_output": True,
                "text": True,
                "timeout": 120,
                "cwd": str(file_path.parent),
            }
            if os.name == "nt":
                babel_kwargs["shell"] = True
            result = subprocess.run(babel_cmd, **babel_kwargs)
            if result.returncode == 0:
                syntax_results.append(True)
            else:
                detail = (result.stderr or result.stdout or "babel parse failed").strip()
                error_message("CriticTools", f"JS syntax error in {file_path.name}: {detail[:300]}")
                syntax_results.append(False)

        def _run_command(command: list[str], cwd: Path, label: str, timeout: int = 180) -> bool:
            run_kwargs: dict[str, Any] = {
                "cwd": str(cwd),
                "capture_output": True,
                "text": True,
                "timeout": timeout,
            }
            if os.name == "nt" and command and command[0] in {"npm", "npx"}:
                run_kwargs["shell"] = True
            result = subprocess.run(command, **run_kwargs)
            if result.returncode == 0:
                executable_results.append(True)
                return True
            detail = (result.stderr or result.stdout or f"{label} failed").strip()
            error_message("CriticTools", f"{label}: {detail[:300]}")
            executable_results.append(False)
            return False

        try:
            zip_bytes = base64.b64decode(code_text, validate=True)
            temp_dir = tempfile.TemporaryDirectory(prefix="critic-eval-")
            project_root = Path(temp_dir.name)
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                zf.extractall(project_root)
        except Exception:
            _check_python_syntax(code_text, "inline code")
            syntax_score = 100.0 if syntax_results and all(syntax_results) else 0.0
            result = {
                "syntax_score": syntax_score,
                "executable_score": 0.0,
                "overall_score": round(syntax_score / 2, 2),
            }
            success_message("CriticTools", {"syntax_executable": result})
            return result

        try:
            backend_dir = project_root / "backend"
            frontend_dir = project_root / "frontend"

            for file_path in project_root.rglob("*"):
                if not file_path.is_file():
                    continue
                suffix = file_path.suffix.lower()
                if suffix == ".py":
                    try:
                        _check_python_syntax(
                            file_path.read_text(encoding="utf-8"),
                            str(file_path.relative_to(project_root)),
                        )
                    except OSError as exc:
                        error_message("CriticTools", f"Failed to read {file_path.name}: {exc}")
                        syntax_results.append(False)
                elif suffix in {".js", ".jsx"}:
                    _check_js_syntax(file_path)

            if backend_dir.is_dir():
                requirements = backend_dir / "requirements.txt"
                if requirements.is_file():
                    _run_command(
                        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                        backend_dir,
                        "backend pip install",
                        timeout=180,
                    )
                if any(backend_dir.rglob("*.py")):
                    _run_command(
                        [sys.executable, "-m", "compileall", "-q", "."],
                        backend_dir,
                        "backend compileall",
                        timeout=120,
                    )

            if frontend_dir.is_dir() and (frontend_dir / "package.json").is_file():
                npm_install_ok = _run_command(
                    ["npm", "install"],
                    frontend_dir,
                    "frontend npm install",
                    timeout=300,
                )
                if npm_install_ok:
                    _run_command(
                        ["npx", "vite", "build"],
                        frontend_dir,
                        "frontend vite build",
                        timeout=300,
                    )
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

        if not syntax_results:
            error_message("CriticTools", "No Python/JS source files found for syntax scoring")
            syntax_score = 0.0
        else:
            syntax_score = round((sum(syntax_results) / len(syntax_results)) * 100, 2)

        if not executable_results:
            executable_score = 0.0
        else:
            executable_score = round((sum(executable_results) / len(executable_results)) * 100, 2)

        result = {
            "syntax_score": syntax_score,
            "executable_score": executable_score,
            "overall_score": round((syntax_score + executable_score) / 2, 2),
        }
        success_message(
            "CriticTools",
            {
                "syntax_executable": {
                    **result,
                    "syntax_checks": len(syntax_results),
                    "executable_checks": len(executable_results),
                }
            },
        )
        return result

    def generate_code_evaluation(
        self,
        project_name: str,
        opl_id: str,
        code: str,
        metrics: list[dict[str, Any]] | dict[str, Any],
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """
        Produce code-level evaluation results

        Parameters:
            - project_name : The project name
            - opl_id : The OPL ID
            - code : The generated code
            - metrics : The evaluation metrics
            - tool_context : Session state (reads code_coverage_graph)

        Returns:
            - dict[str, Any] : The evaluation results
        """
        start_message("CriticTools", "Generate code evaluation for " + project_name)

        graph_metric: dict[str, Any] | None = None
        syntax_metric: dict[str, Any] | None = None

        if isinstance(metrics, dict):
            graph_metric = metrics.get("graph_coverage")
            syntax_metric = metrics.get("code_bleu")
        elif isinstance(metrics, list):
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                name = str(metric.get("name", "")).lower()
                if "graph" in name and "coverage" in name:
                    graph_metric = metric
                elif any(
                    token in name
                    for token in ("syntax", "executable", "bleu", "code bleu")
                ):
                    syntax_metric = metric

        if not graph_metric or not syntax_metric:
            error_message("CriticTools", "No graph coverage or syntax/executable metric found")
            return {
                "status": "error",
                "message": "No graph coverage or syntax/executable metric found",
            }

        graph_weight = float(graph_metric.get("weight") or 0.0)
        syntax_weight = float(syntax_metric.get("weight") or 0.0)
        total_weight = graph_weight + syntax_weight or 1.0

        code_coverage_graph = tool_context.state.get("code_coverage_graph")
        coverage_scores = self._graph_coverage_score(opl_id, code_coverage_graph, tool_context)
        syntax_scores = self._syntax_and_executable_score(code)

        graph_coverage_score = coverage_scores["overall_score"]
        syntax_and_executable_score = syntax_scores["overall_score"]
        overall_score = round(
            (
                graph_coverage_score * graph_weight
                + syntax_and_executable_score * syntax_weight
            )
            / total_weight,
            2,
        )

        evaluation = {
            "graph_coverage": {
                "score": graph_coverage_score,
                "breakdown": {
                    "entity_score": coverage_scores["entity_score"],
                    "state_score": coverage_scores["state_score"],
                    "relation_score": coverage_scores["relation_score"],
                },
            },
            "syntax_and_executable": {
                "score": syntax_and_executable_score,
                "breakdown": {
                    "syntax_score": syntax_scores["syntax_score"],
                    "executable_score": syntax_scores["executable_score"],
                },
            },
            "overall_score": overall_score,
        }
        tool_context.state["code_evaluation"] = evaluation

        response = self._db.save_opl_evaluation_scores(opl_id, evaluation)
        if response.get("status") != "success":
            error_message("CriticTools", response.get("message"))
            return {"status": "error", "message": response.get("message")}

        success_message("CriticTools", {"evaluation": evaluation})
        return {"status": "success", "evaluation": evaluation}

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
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


def get_project_download_name(state: dict[str, Any], default: str = "generated_code.zip") -> str:
    """Return a zip download filename from session state, or *default*."""
    slug = state.get("project_slug")
    if isinstance(slug, str) and slug.strip():
        return f"{slug.strip()}.zip"
    return default


def get_project_zip_from_state(state: dict[str, Any]) -> str | None:
    """
    Return a base64 project zip from session state if present and valid.

    Does not re-run code generation; the agent must have produced the zip via
    ``generate_code`` (or ``finish_code_zip_base64`` from ``finish_and_return_user``).
    """
    zip_b64 = state.get("finish_code_zip_base64") or state.get("generated_code_zip")
    if not zip_b64:
        return None
    try:
        if is_valid_project_zip(base64.b64decode(zip_b64)):
            return zip_b64
    except Exception:
        pass
    return None
