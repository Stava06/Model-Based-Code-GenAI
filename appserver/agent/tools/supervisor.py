from __future__ import annotations
import base64
import io
import json
import os
import re
import zipfile
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from agent.memory import DBconnection
from agent.opl_examples import demo1
from messages import start_message, error_message, success_message, info_message
from extensions import call_gemini
from config import CONFIG

# Get the agent debug type
AGENT_DEBUG = CONFIG["server"]["agent_debug"]

# Directory holding the raw training files used to build the OPL logic map.
_TRAINING_FILES_DIR = os.path.join(os.path.dirname(__file__), "train", "files")

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

    def get_opl(self, opl_id: str, tool_context: ToolContext) -> dict[str, Any]:
        """
            Resolve OPL by id and store it in session ``opl``.

            Parameters:
                - opl_id : The ID of the OPL
                - tool_context : The tool context

            Returns:
                - dict[str, Any] : ``{"status": "success", "data": opl}`` or an error dict
        """
        start_message("SupervisorTools", f"Get OPL by id {opl_id}")

        if AGENT_DEBUG != 1 and AGENT_DEBUG != 4:
            success_message("SupervisorTools", "Returning demo OPL")
            tool_context.state["opl"] = demo1
            return {"status": "success", "data": demo1}

        if not opl_id:
            #TODO: Get opl from Local Storage
            tool_context.state["opl"] = demo1
            return {"status": "success", "data": demo1}

        response = self._db.get_opl(opl_id)
        if response.get("status") == "success":
            opl_retrieved = response.get("data")
            tool_context.state["opl"] = opl_retrieved
            success_message("SupervisorTools", {"opl length": len(opl_retrieved) if opl_retrieved else 0})
            return {"status": "success", "data": opl_retrieved}

        error_message("SupervisorTools", response.get("message"))
        return {"status": "error", "message": response.get("message")}

    def supervisor_first_step(
        self, tool_context: ToolContext, opl: str | None = None, opl_id: str | None = None
    ) -> dict[str, Any]:
        """
            Complete supervisor initial start and hand off to the generator.

            Pass OPL text from ``get_opl`` (or rely on the ``opl`` already stored in
            session by ``get_opl``). Persists ``opl`` in session, sets ``cnt_itr`` to 0,
            ``initial_start`` to False, and ``current_role`` to ``generator``.
        """
        start_message("SupervisorTools", "supervisor_first_step")

        opl_text = (opl or tool_context.state.get("opl") or "").strip()
        if not opl_text:
            error_message("SupervisorTools", "supervisor_first_step: missing opl")
            return {
                "status": "error",
                "message": "opl is required (call get_opl first, or pass the OPL text)",
            }

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

    # Session keys that ``change_session`` is allowed to overwrite. Control-flow
    # keys (current_role, cnt_itr, initial_start, train, max_itr, ...) are excluded
    # on purpose so a resolution can never corrupt the orchestration loop.
    _CHANGEABLE_SESSION_KEYS = (
        "opl",
        "opl_logic_map",
        "project_name",
        "project_slug",
        "code_coverage_graph",
        "evaluation_metrics",
        "code_evaluation",
    )

    def _build_problem_context(self, message: str, state: Any) -> dict[str, Any]:
        """
            Build a compact, JSON-serializable snapshot of session state for Gemini.

            Parameters:
                - message : The problem message
                - state : The session state

            Returns:
                - dict[str, Any] : The problem context
        """
        opl = state.get("opl") or ""
        return {
            "problem": message,
            "opl": opl[:4000],
            "opl_logic_map": state.get("opl_logic_map"),
            "code_evaluation": state.get("code_evaluation"),
            "last_completed_role": state.get("last_completed_role"),
            "current_role": state.get("current_role"),
            "project_name": state.get("project_name"),
            "has_generated_code": bool(state.get("generated_code_zip")),
            "iteration": state.get("cnt_itr"),
            "max_iteration": state.get("max_itr"),
            "changeable_session_keys": list(self._CHANGEABLE_SESSION_KEYS),
        }

    def _problem_resolution_prompt(self, context: dict[str, Any]) -> str:
        """
            Build the Gemini prompt that decides how to resolve a workflow problem.

            Parameters:
                - context : The problem context from ``_build_problem_context``

            Returns:
                - str : The resolution prompt
        """
        return (
            "You are the Supervisor's problem-resolution brain for an OPL-to-code "
            "generation workflow. A workflow problem was reported. Decide the single "
            "best action to recover, and return the data needed to apply it.\n\n"
            "Choose exactly one `action`:\n"
            "- \"change_opl_logic\": The OPL logic map is wrong/incomplete. First build "
            "your own understanding of the problem from the `problem`, the `opl` "
            "specification, and the `code_evaluation` feedback: identify which "
            "objects, processes, or relations the current `opl_logic_map` is missing, "
            "mislabeling, or mapping to the wrong OPM type. Then return an improved "
            "`opl_logic_map` object with `objects`, `processes`, and `relations` keys "
            "that resolves those gaps. Keep the same schema and shape as the current "
            "map (each key holds the type definitions/descriptions used to classify OPL "
            "relations), preserve every correct entry, and only add, remove, or refine "
            "entries that your analysis shows are needed to fix the reported problem.\n"
            "- \"handoff\": A role should re-run its workflow. Set `next_role` to "
            "\"generator\" (rebuild the code) or \"critic\" (re-evaluate the code).\n"
            "- \"change_session\": A specific session memory value is wrong. Set "
            "`session_key` (one of changeable_session_keys) and `session_value` to a "
            "corrected value generated by you.\n"
            "- \"cant_solve\": The problem cannot be recovered automatically. Set "
            "`user_error` to a clear, user-facing explanation.\n\n"
            "Return ONLY a JSON object with this schema (omit keys not relevant to the "
            "chosen action):\n"
            "{\n"
            '  "action": "change_opl_logic | handoff | change_session | cant_solve",\n'
            '  "reason": "short explanation of the decision",\n'
            '  "next_role": "generator | critic | null",\n'
            '  "opl_logic_map": { "objects": ..., "processes": ..., "relations": ... },\n'
            '  "session_key": "one of changeable_session_keys",\n'
            '  "session_value": "corrected value for that key",\n'
            '  "user_error": "user-facing error message"\n'
            "}\n\n"
            "Workflow context:\n"
            f"{json.dumps(context, indent=2, default=str)}"
        )

    def _resolve_problem_with_gemini(self, message: str, state: Any) -> dict[str, Any]:
        """
            Ask Gemini how to resolve a workflow problem.

            Parameters:
                - message : The problem message
                - state : The session state

            Returns:
                - dict[str, Any] : The parsed resolution, or a ``cant_solve`` fallback
        """
        context = self._build_problem_context(message, state)
        prompt = self._problem_resolution_prompt(context)

        result = call_gemini(prompt)
        if result.get("status") != "success":
            error_message("SupervisorTools", result.get("message", "Gemini resolution failed"))
            return {
                "action": "cant_solve",
                "reason": "Gemini could not produce a resolution",
                "user_error": message,
            }

        try:
            resolution = json.loads(_strip_code_fences(result.get("data", "")))
        except json.JSONDecodeError as exc:
            error_message("SupervisorTools", f"Invalid resolution JSON from Gemini: {exc}")
            return {
                "action": "cant_solve",
                "reason": f"Invalid resolution JSON: {exc}",
                "user_error": message,
            }

        if not isinstance(resolution, dict):
            return {
                "action": "cant_solve",
                "reason": "Gemini resolution was not a JSON object",
                "user_error": message,
            }
        return resolution

    def _generate_opl_logic_map_prompt(self, files: list[str]) -> str:
        """
        Generate the prompt for the OPL logic map generation.

        Parameters:
            - files : The training file contents

        Returns:
            - str : The prompt
        """

        file_prompt = ""
        for index, file in enumerate(files):
            file_prompt += f"File {index + 1}:\n{file}\n"

        schema = (
            "{\n"
            '  "objects": "Object: <explanation>\\nState: <explanation>\\n...",\n'
            '  "processes": "Process: <explanation>\\nTransformation: <explanation>\\n...",\n'
            '  "relations": "Aggregation-Participation: <explanation>\\n..."\n'
            "}"
        )

        return (
            "You are the OPL logic map generator Agent. Generate the OPL logic map from "
            "the files.\n\n"
            f"The files are:\n{file_prompt}\n"
            "Return ONLY a valid JSON object with exactly these three keys: objects, "
            "processes, relations. Each value is a single newline-separated string of "
            "'<Term>: <explanation>' lines.\n\n"
            f"Schema:\n{schema}\n\n"
        )

    def generate_problem(self, message: str, tool_context: ToolContext) -> dict[str, Any]:
        """
            Resolve a workflow problem with Gemini, apply the fix, hand back to Supervisor.

            Records the problem, asks Gemini for the best recovery action, applies it,
            and (except for ``cant_solve``) sets ``current_role`` back to ``supervisor``.
            The returned dict tells the Supervisor what happened and which role to run next.

            Parameters:
                - message : The problem message
                - tool_context : The tool context

            Returns:
                - dict[str, Any] : The resolution result
        """
        start_message("SupervisorTools", "Generate problem")

        state = tool_context.state
        state["workflow_problem"] = message

        resolution = self._resolve_problem_with_gemini(message, state)
        action = str(resolution.get("action") or "cant_solve").strip()
        reason = str(resolution.get("reason") or "")

        result: dict[str, Any] = {
            "status": "success",
            "action": action,
            "problem": message,
            "reason": reason,
        }

        # The Critic's failing evaluation is stale the moment we apply a fix and hand a
        # role back for a redo. Clear it so the Supervisor's problem check stops re-reading
        # the old low score and instead routes through the Critic again to re-evaluate the
        # regenerated code. (State has no delete, so None is the cleared value.)
        if action != "cant_solve":
            state["code_evaluation"] = None

        if action == "change_opl_logic":
            opl_logic_map = resolution.get("opl_logic_map")
            if not isinstance(opl_logic_map, dict) or not opl_logic_map:
                error_message("SupervisorTools", "change_opl_logic missing a valid opl_logic_map")
                action = "cant_solve"
                resolution["user_error"] = "Could not improve the OPL logic map"
            else:
                state["opl_logic_map"] = opl_logic_map

                # Persist the improved logic map so the Generator/Critic read it from the DB.
                save_response = self._db.save_opl_logic_map(opl_logic_map)
                if save_response.get("status") == "success":
                    success_message("SupervisorTools", save_response.get("message"))
                else:
                    error_message("SupervisorTools", save_response.get("message", "Failed to save OPL logic map"))
                result["saved"] = save_response.get("status") == "success"

                next_role = str(resolution.get("next_role") or "generator").strip().lower()
                if next_role not in {"generator", "critic"}:
                    next_role = "generator"
                state["next_role"] = next_role
                state["current_role"] = "supervisor"
                result["next_role"] = next_role
                result["message"] = (
                    "Improved OPL logic map saved to session and database. "
                    f"Hand off to {next_role} to redo the workflow."
                )

                state["opl_reference_graph"] = None

                success_message("SupervisorTools", {"action": action, "next_role": next_role})
                return result

        if action == "handoff":
            next_role = str(resolution.get("next_role") or "").strip().lower()
            if next_role not in {"generator", "critic"}:
                error_message("SupervisorTools", f"handoff has invalid next_role: {next_role!r}")
                action = "cant_solve"
                resolution["user_error"] = "No valid role to hand off to"
            else:
                state["next_role"] = next_role
                state["current_role"] = "supervisor"
                result["next_role"] = next_role
                result["message"] = f"Hand off to {next_role} to redo the workflow."
                success_message("SupervisorTools", {"action": action, "next_role": next_role})
                return result

        if action == "change_session":
            session_key = str(resolution.get("session_key") or "").strip()
            if session_key == "opl_reference_graph":
                state["opl_reference_graph"] = None

            if session_key not in self._CHANGEABLE_SESSION_KEYS:
                error_message("SupervisorTools", f"change_session has invalid key: {session_key!r}")
                action = "cant_solve"
                resolution["user_error"] = "No valid session key to change"
            elif "session_value" not in resolution:
                error_message("SupervisorTools", "change_session missing session_value")
                action = "cant_solve"
                resolution["user_error"] = "No replacement value for session key"
            else:
                state[session_key] = resolution.get("session_value")
                next_role = str(resolution.get("next_role") or "generator").strip().lower()
                if next_role not in {"generator", "critic"}:
                    next_role = "generator"
                state["next_role"] = next_role
                state["current_role"] = "supervisor"
                result["next_role"] = next_role
                result["session_key"] = session_key
                result["message"] = (
                    f"Updated session memory '{session_key}'. "
                    f"Hand off to {next_role} to redo the workflow."
                )
                
                success_message("SupervisorTools", {"action": action, "session_key": session_key})
                return result

        # cant_solve (either chosen by Gemini or fallen back to from a failed action)
        user_error = str(resolution.get("user_error") or message)
        state["workflow_problem"] = user_error
        state["current_role"] = "supervisor"
        result["status"] = "error"
        result["action"] = "cant_solve"
        result["message"] = user_error
        error_message("SupervisorTools", {"action": "cant_solve", "message": user_error})
        return result

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
        project_name = tool_context.state.get("project_name") or "Undefined Project Name"
        project_slug = tool_context.state.get("project_slug") or "undefined-project-slug"

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

    def get_training_files(self) -> dict[str, Any]:
        """
            Load training files for OPL logic map generation.

            Returns:
                - dict[str, Any] : The training files
        """
        start_message("SupervisorTools", "Get training files")

        if not os.path.isdir(_TRAINING_FILES_DIR):
            error_message("SupervisorTools", f"Training files directory not found: {_TRAINING_FILES_DIR}")
            return {"status": "error", "message": "Training files directory not found"}

        training = []
        count = 0
        for name in sorted(os.listdir(_TRAINING_FILES_DIR)):
            path = os.path.join(_TRAINING_FILES_DIR, name)
            if not os.path.isfile(path):
                continue

            try:
                with open(path, "r", encoding="utf-8") as fh:
                    file_content = fh.read()
            except (OSError, UnicodeDecodeError) as exc:
                info_message("SupervisorTools", f"Skipping training file {name}: {exc}")
                continue

            if not file_content:
                info_message("SupervisorTools", f"Training file {name} is empty")
                continue

            training.append(file_content)
            count += len(file_content)
            info_message("SupervisorTools", f"Training file {name} loaded")

        if not training:
            error_message("SupervisorTools", "No training files loaded")
            return {"status": "error", "message": "No training files loaded"}

        success_message("SupervisorTools", f"Loaded {len(training)} training files with {count} characters")
        return {"status": "success", "training_files": training}

    def generate_opl_logic_map(self, files: list[str], tool_context: ToolContext) -> dict[str, Any]:
        """
            Build the OPL logic map from training files and store it in session.

            Parameters:
                - files : The training file contents
                - tool_context : The tool context

            Returns:
                - dict[str, Any] : ``{"status": "success", "opl_logic_map": {...}}`` or an error dict
        """
        start_message("SupervisorTools", "Generate OPL logic map")

        prompt = self._generate_opl_logic_map_prompt(files)
        result = call_gemini(prompt)
        if result.get("status") != "success":
            error_message("SupervisorTools", result.get("message", "OPL logic map generation failed"))
            return {"status": "error", "message": result.get("message", "OPL logic map generation failed")}

        try:
            opl_logic_map = json.loads(_strip_code_fences(result.get("data", "")))
        except json.JSONDecodeError as exc:
            error_message("SupervisorTools", f"Invalid OPL logic map JSON from Gemini: {exc}")
            return {"status": "error", "message": f"Invalid OPL logic map JSON: {exc}"}

        if not isinstance(opl_logic_map, dict) or not opl_logic_map:
            error_message("SupervisorTools", "OPL logic map must be a non-empty object")
            return {"status": "error", "message": "OPL logic map must be a non-empty object"}

        tool_context.state["opl_logic_map"] = opl_logic_map
        success_message("SupervisorTools", {"opl_logic_map_keys": list(opl_logic_map.keys())})
        return {"status": "success", "opl_logic_map": opl_logic_map}

    def save_opl_logic_map(self, opl_logic_map: dict[str, Any]) -> dict[str, Any]:
        """
            Persist the OPL logic map to the database.

            Parameters:
                - opl_logic_map : The OPL logic map

            Returns:
                - dict[str, Any] : The result
        """
        start_message("SupervisorTools", "Save OPL logic map")

        response = self._db.save_opl_logic_map(opl_logic_map)
        if response.get("status") == "success":
            success_message("SupervisorTools", "OPL logic map saved to database")
            return response
        else:
            error_message("SupervisorTools", response.get("message"))
            return None

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_opl,
            self.supervisor_first_step,
            self.generate_problem,
            self.finish_and_return_user,
            self.get_training_files,
            self.generate_opl_logic_map,
            self.save_opl_logic_map,
        ]