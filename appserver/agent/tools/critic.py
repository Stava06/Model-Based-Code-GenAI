from __future__ import annotations
import ast
import base64
import io
import json
import re
import zipfile
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from agent.memory import DBconnection
from agent.examples.eval_metrics_example import metrics_example
from agent.examples.eval_example import evaluation_example
from messages import start_message, error_message, success_message
from extensions import call_gemini
from agent.tool_helpers.create_folder_dir import coverage_graph_schema

from agent.tool_helpers.coverage_graph import (
    canonicalize_coverage_graph,
    coerce_coverage_graph,
    graph_similarity_score,
)
from agent.tool_helpers.execution_readiness import (
    run_execution_readiness_checks,
    execution_readiness_score,
)
from config import CONFIG

# Get the agent debug type
AGENT_DEBUG = CONFIG["server"]["agent_debug"]

def _zip_normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")

def _zip_file_map(zip_bytes: bytes) -> dict[str, str]:
    files: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            normalized = _zip_normalize_path(name)
            try:
                files[normalized] = zf.read(name).decode("utf-8")
            except UnicodeDecodeError:
                files[normalized] = ""
    return files

def _check_js_structure(source: str) -> bool:
    """Lightweight JS/JSX syntax sanity check without Node or subprocess."""
    if not source.strip():
        return False

    stack: list[str] = []
    in_string: str | None = None
    escape = False
    pairs = {"(": ")", "[": "]", "{": "}"}

    for ch in source:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if in_string:
            if ch == in_string:
                in_string = None
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            continue
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False

    return not stack and in_string is None

def _check_python_syntax(source: str) -> bool:
    try:
        ast.parse(source)
        compile(source, "<generated>", "exec")
        return True
    except (SyntaxError, ValueError):
        return False

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
        self._eval_metrics = {
            "graph_coverage": {
                "weight": 0.5,
                "description": (
                    "The graph is fully covered, which means all the objects and "
                    "processes of the given OPL are represented in the code"
                ),
            },
            "execution_and_syntax": {
                "weight": 0.5,
                "description": "Syntax-valid code and static execution-readiness checks ",
            },
        }
        self.graph_coverage_scores = None

    def _gemini_reference_graph_prompt(self, opl_logic_map: dict[str, Any], opl: str) -> str:
        """
            Gemini prompt used to generate the OPL reference graph

            params:
                - opl_logic_map : The OPL logic map
                - opl : The OPL

            returns:
                - str : The Gemini prompt
        """

        return f"""
            You are analyzing an OPL (Object-Process Language) specification. Extract every object 
            and process from the OPL into a coverage graph. Put states in each node's states[] array — 
            never as separate top-level nodes. Use this logic map to map each relation to the closest 
            relation type (objects, processes, and relations sections):
            {json.dumps(opl_logic_map, indent=2)}
            
            OPL specification:
            {opl}

            Return only valid JSON with this schema:
            {coverage_graph_schema()}
        """

    def _parse_gemini_graph_response(raw: str) -> dict[str, Any] | None:
        """
            Parse the Gemini graph response

            params:
                - raw : The raw text to parse

            returns:
                - dict[str, Any] | None : The parsed graph
        """
        try:
            # Strip the code fences from the raw text
            text = raw.strip()
            match = re.match(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
            text = match.group(1).strip() if match else text

            # Parse the JSON
            payload = json.loads(text)
        except Exception:
            error_message("CriticTools", "Invalid graph JSON from Gemini")
            return None

        # Coerce the coverage graph
        coerced = coerce_coverage_graph(payload)
        if coerced is None or not isinstance(coerced.get("nodes"), list):
            error_message("CriticTools", "Gemini response missing nodes array")
            return None

        return canonicalize_coverage_graph(coerced)

    def _generate_opl_reference_graph(self, opl_id: str) -> dict[str, Any] | None:
        """
            Generate the OPL reference graph using Gemini

            params:
                - opl_id : The opl id

            returns:
                - dict[str, Any] | None : The OPL reference graph
        """
        # Get the latest OPL logic map from the database
        logic_map_response = self._db.get_latest_opl_logic_map()

        # Get the OPL from the database
        opl_response = self._db.get_opl(opl_id)

        # Check if the logic map response is successful
        if logic_map_response.get("status") != "success":
            error_message("CriticTools", logic_map_response.get("message", "Failed to load logic map"))
            return None

        # Check if the OPL response is successful
        if opl_response.get("status") != "success":
            error_message("CriticTools", opl_response.get("message", f"Failed to load OPL: {opl_id}"))
            return None

        opl_logic_map = logic_map_response.get("data", {}).get("opl_logic_map", {})
        opl = opl_response.get("data", "")
        prompt = self._gemini_reference_graph_prompt(opl_logic_map, opl)

        # Call the Gemini API to generate the OPL reference graph
        result = call_gemini(prompt)
        if result.get("status") != "success":
            error_message("CriticTools", result.get("message", "Gemini graph extraction failed"))
            return None

        # Parse the Gemini graph response
        parsed = self._parse_gemini_graph_response(result.get("data", ""))
        return parsed

    def _get_opl_reference_graph(self, opl_id: str, tool_context: ToolContext | None = None) -> dict[str, Any] | None:
        """
            Get the OPL reference graph

            params:
                - opl_id : The opl id
                - tool_context : The tool context

            returns:
                - dict[str, Any] | None : The OPL reference graph
        """
        # Check if exists an opl reference graph
        if tool_context is not None:
            cached = tool_context.state.get("opl_reference_graph")
            if isinstance(cached, dict) and isinstance(cached.get("nodes"), list):
                return cached

        # Create the opl reference graph
        opl_coverage_graph = self._generate_opl_reference_graph(opl_id)
        if tool_context is not None and opl_coverage_graph is not None:
            tool_context.state["opl_reference_graph"] = opl_coverage_graph
            
        return opl_coverage_graph

    def _graph_coverage_score(self, opl_id: str, code_coverage_graph: dict[str, Any], tool_context: ToolContext | None = None) -> None:
        """
            Calculate the graph coverage score

            params:
                - opl_id : The opl id
                - code_coverage_graph : The code coverage graph
                - tool_context : The tool context

            returns:
                - None
        """
        # Check if code coverage graph is defined
        if not code_coverage_graph or not isinstance(code_coverage_graph, dict):
            error_message("CriticTools", "No code_coverage_graph given")
            return 

        # Check if code coverage graph has nodes
        if not code_coverage_graph.get("nodes"):
            error_message("CriticTools", "code_coverage_graph has no nodes")
            return 

        # Create the OPL reference graph
        opl_coverage_graph = self._get_opl_reference_graph(opl_id, tool_context)
        if opl_coverage_graph is None:
            error_message("CriticTools", "Could not build OPL reference graph",)
            return 

        # Calculate the graph coverage score
        self.graph_coverage_scores = graph_similarity_score(opl_coverage_graph, code_coverage_graph)

        msg = {key: value for key, value in self.graph_coverage_scores.items() if key.split("_")[1] != "score"}
        success_message("CriticTools", {"graph_coverage": msg})

    def _decode_project_zip(self, code_zip_b64: str) -> bytes | None:
        code_text = str(code_zip_b64).strip()
        if not code_text:
            return None
        for validate in (True, False):
            try:
                zip_bytes = base64.b64decode(code_text, validate=validate)
                if is_valid_project_zip(zip_bytes):
                    return zip_bytes
            except Exception:
                continue
        return None

    def _syntax_and_executable_score(self, code_zip_b64: str) -> dict[str, float]:
        empty = {"syntax_score": 0.0, "executable_score": 0.0, "overall_score": 0.0}
        zip_bytes = self._decode_project_zip(code_zip_b64)
        if zip_bytes is None:
            error_message(
                "CriticTools",
                "No valid project zip for syntax/executable scoring "
                "(expected base64-encoded zip with frontend/ and backend/)",
            )
            return empty

        syntax_results: list[bool] = []
        files = _zip_file_map(zip_bytes)

        for path, source in sorted(files.items()):
            suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if suffix == "py":
                ok = _check_python_syntax(source)
                syntax_results.append(ok)
                if not ok:
                    error_message("CriticTools", f"Python syntax error in {path}")
            elif suffix == "json":
                try:
                    json.loads(source)
                    syntax_results.append(True)
                except json.JSONDecodeError as exc:
                    error_message("CriticTools", f"JSON syntax error in {path}: {exc}")
                    syntax_results.append(False)
            elif suffix in {"js", "jsx"}:
                ok = _check_js_structure(source)
                syntax_results.append(ok)
                if not ok:
                    error_message("CriticTools", f"JS/JSX structure error in {path}")

        execution_checks = run_execution_readiness_checks(files)
        execution_summary = execution_readiness_score(execution_checks)
        for check in execution_checks:
            if not check.passed:
                detail = f"{check.name}: {check.detail}" if check.detail else check.name
                error_message("CriticTools", f"Execution readiness failed — {detail}")

        if not syntax_results:
            error_message("CriticTools", "No Python/JS source files found for syntax scoring")
            syntax_score = 0.0
        else:
            syntax_score = round((sum(syntax_results) / len(syntax_results)) * 100, 2)

        executable_score = float(execution_summary["executable_score"])

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
                    "execution_checks": len(execution_checks),
                    "execution_passed": execution_summary["passed_checks"],
                    "execution_failed": execution_summary["failed_checks"],
                    "execution_failures": execution_summary["failures"],
                }
            },
        )
        return result

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """
            Fetch metrics for code evaluation

            returns:
                - dict[str, Any] : The evaluation metrics
        """
        start_message("CriticTools", "Get evaluation metrics")

        if AGENT_DEBUG != 3 and AGENT_DEBUG != 4:
            success_message("CriticTools", "Returning demo evaluation metrics")
            return metrics_example

        success_message("CriticTools", {"metrics": {key for key in self._eval_metrics}})
        return self._eval_metrics

    def generate_code_evaluation(self, tool_context: ToolContext) -> dict[str, Any]:
        """
            Generate code evaluation results

            params:
                - tool_context : The tool context

            returns:
                - dict[str, Any] : The code evaluation results
        """
        project_name = (tool_context.state.get("project_name") or "OPL Project").strip()
        opl_id = (tool_context.state.get("opl_id") or "").strip()
        metrics = tool_context.state.get("evaluation_metrics")

        start_message("CriticTools", "Generate code evaluation for " + project_name)

        # Record that the Critic completed so the Supervisor can route correctly.
        tool_context.state["last_completed_role"] = "critic"

        if AGENT_DEBUG != 3 and AGENT_DEBUG != 4:
            success_message("CriticTools", "Returning demo code evaluation")
            return evaluation_example

        # Check if the opl_id is in the session
        if not opl_id:
            error_message("CriticTools", "No opl_id in session")
            return {"status": "error", "message": "No opl_id in session"}

        # Check if the evaluation metrics are in the session
        if not metrics or not isinstance(metrics, dict):
            error_message("CriticTools", "No evaluation metrics in session")
            return {"status": "error", "message": "No evaluation metrics in session"}

        graph_metric = metrics.get("graph_coverage")
        exec_syntax_metric = metrics.get("execution_and_syntax")

        # Check if the graph coverage or syntax/executable metric is found
        if not graph_metric or not exec_syntax_metric:
            error_message("CriticTools", "No graph coverage or syntax/executable metric found")
            return {
                "status": "error",
                "message": "No graph coverage or syntax/executable metric found",
            }

        graph_weight = float(graph_metric.get("weight") or 0.0)
        exec_syntax_weight = float(exec_syntax_metric.get("weight") or 0.0)
        total_weight = graph_weight + exec_syntax_weight or 1.0

        # Get the generated code zip from the session
        code_zip_b64 = tool_context.state.get("finish_code_zip_base64") or tool_context.state.get("generated_code_zip")
        
        # Check if the generated code zip is in the session
        if not code_zip_b64:
            error_message("CriticTools", "No generated_code_zip in session for syntax/executable scoring")
            return {
                "status": "error",
                "message": "No generated code zip in session. Run generate_code first.",
            }

        # Get the code coverage graph from the session
        raw_graph = tool_context.state.get("code_coverage_graph")
        code_coverage_graph = canonicalize_coverage_graph(raw_graph) if isinstance(raw_graph, dict) else None

        # Evaluate based on metrics
        self._graph_coverage_score(opl_id, code_coverage_graph, tool_context)
        syntax_scores = self._syntax_and_executable_score(code_zip_b64)

        graph_coverage_score = self.graph_coverage_scores["overall_score"]
        syntax_and_executable_score = syntax_scores["overall_score"]
        overall_score = round(
            (
                graph_coverage_score * graph_weight
                + syntax_and_executable_score * exec_syntax_weight
            )
            / total_weight,
            2,
        )

        evaluation = {
            "graph_coverage": {
                "score": graph_coverage_score,
                "breakdown": {
                    "entity_score": self.graph_coverage_scores["entity_score"],
                    "state_score": self.graph_coverage_scores["state_score"],
                    "relation_score": self.graph_coverage_scores["relation_score"],
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