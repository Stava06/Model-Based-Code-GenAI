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
from messages import start_message, error_message, success_message, info_message
from extensions import call_gemini
from agent.tool_helpers.create_folder_dir import coverage_graph_schema

from agent.tool_helpers.coverage_graph import (
    GRAPH_COVERAGE_SCORE_DEFAULT,
    canonicalize_coverage_graph,
    coerce_coverage_graph,
    graph_similarity_score,
)
from agent.tool_helpers.execution_readiness import (
    run_execution_readiness_checks,
    execution_readiness_score,
)
from agent.tool_helpers.js_syntax import check_js_syntax
from config import CONFIG

# Get the agent debug type
AGENT_DEBUG = CONFIG["server"]["agent_debug"]

class CriticTools:
    """
        Critic Tools — code evaluation against OPL specification

        Includes:
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

    def _check_python_syntax(self, source: str) -> bool:
        """
            Check the Python syntax of the source code

            params:
                - source : The source code

            returns:
                - bool : True if the Python syntax is valid, False otherwise
        """
        try:
            ast.parse(source)
            compile(source, "<generated>", "exec")
            return True
        except Exception:
            return False

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

    def _parse_gemini_graph_response(self, raw: str) -> dict[str, Any] | None:
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

    def _graph_coverage_score(
        self,
        opl_id: str,
        code_coverage_graph: dict[str, Any] | None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, float]:
        """
            Calculate the graph coverage score

            params:
                - opl_id : The opl id
                - code_coverage_graph : The code coverage graph
                - tool_context : The tool context

            returns:
                - dict[str, float] : Coverage scores (zeros when scoring cannot run)
        """
        scores = GRAPH_COVERAGE_SCORE_DEFAULT.copy()

        # Check if code coverage graph is defined
        if not code_coverage_graph or not isinstance(code_coverage_graph, dict):
            error_message("CriticTools", "No code_coverage_graph given")
            return scores

        # Check if code coverage graph has nodes
        if not code_coverage_graph.get("nodes"):
            error_message("CriticTools", "code_coverage_graph has no nodes")
            return scores

        # Create the OPL reference graph
        opl_coverage_graph = self._get_opl_reference_graph(opl_id, tool_context)
        if opl_coverage_graph is None:
            error_message("CriticTools", "Could not build OPL reference graph",)
            return scores

        # Calculate the graph coverage score
        scores = graph_similarity_score(opl_coverage_graph, code_coverage_graph)

        msg = {key: value for key, value in scores.items() if key.split("_")[1] != "score"}
        success_message("CriticTools", {"graph_coverage": msg})
        return scores

    def _zip_file_map(self, zip_bytes: bytes) -> dict[str, str]:
        """
            Get the file map from the zip bytes

            params:
                - zip_bytes : The zip bytes

            returns:
                - dict[str, str] : The file map
        """
        files: dict[str, str] = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                normalized = name.replace("\\", "/").lstrip("/")
                try:
                    files[normalized] = zf.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    files[normalized] = ""
        return files

    def _syntax_and_executable_score(self, code_zip_string: str) -> dict[str, float]:
        """
            Calculate the syntax and executable score

            params:
                - code_zip_string : The code zip string

            returns:
                - dict[str, float] : The syntax and executable score
        """
        # Define the default scores
        scores = { "syntax_score": 0.0, "executable_score": 0.0, "overall_score": 0.0 }

        # Decode the code zip string
        is_valid = True
        zip_bytes = None
        try:
            zip_bytes = base64.b64decode(code_zip_string.strip())
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                names = zf.namelist()
                
            # Check if the zip contains frontend and backend folders (no single files)
            if "frontend" in names or "backend" in names:
                is_valid = False

            frontend_files = [ n for n in names if n.startswith("frontend/") and not n.endswith("/") ]
            backend_files = [ n for n in names if n.startswith("backend/") and not n.endswith("/")]

            # Check if files aren't empty
            is_valid = is_valid and len(frontend_files) >= 1 and len(backend_files) >= 1
        except Exception:
            pass
        
        # Check if the code zip string is valid
        if not is_valid or zip_bytes is None:
            error_message("CriticTools", "Code zip string is not valid")
            return scores
        
        # Check the syntax of the files
        syntax_results = []
        files = self._zip_file_map(zip_bytes)
        for path, source in sorted(files.items()):
            suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""

            if suffix == "py":
                type_checked = "Python"
                is_valid = self._check_python_syntax(source)
            elif suffix == "json":
                type_checked = "JSON"
                try:
                    json.loads(source)
                    is_valid = True
                except Exception:
                    is_valid = False
            elif suffix in {"js", "jsx"}:
                type_checked = "JS/JSX"
                is_valid = check_js_syntax(source, path=path)
            else:
                continue

            syntax_results.append(is_valid)
            if not is_valid:
                info_message("CriticTools", f"{type_checked} syntax error in {path}")
        
        # Calculate the syntax score
        syntax_score = 0.0
        if not syntax_results:
            error_message("CriticTools", "No Python/JS source files found for syntax scoring")
        else:
            syntax_score = round((sum(syntax_results) / len(syntax_results)) * 100, 2)

        # Evaluate execution readiness score
        execution_checks = run_execution_readiness_checks(files)
        execution_summary = execution_readiness_score(execution_checks)

        # Check if the execution readiness checks passed
        for check in execution_checks:
            if not check.passed:
                info_message("CriticTools", f"Execution readiness failed — {check.name}: {check.detail if check.detail else check.name}")
        
        # Calculate the executable score
        executable_score = float(execution_summary["executable_score"])

        # Set the scores for the syntax and executable score
        scores["syntax_score"] = syntax_score
        scores["executable_score"] = executable_score
        scores["overall_score"] = round((syntax_score + executable_score) / 2, 2)
        success_message("CriticTools", {"syntax_and_executable": scores})
        return scores

    def get_evaluation_metrics(self, tool_context: ToolContext) -> dict[str, Any]:
        """
            Fetch metrics for code evaluation

            params:
                - tool_context : The tool context

            returns:
                - dict[str, Any] : The evaluation metrics
        """
        start_message("CriticTools", "Get evaluation metrics")

        if AGENT_DEBUG != 3 and AGENT_DEBUG != 4:
            info_message("CriticTools", "Returning demo evaluation metrics")
            metrics = metrics_example
        else:
            metrics = self._eval_metrics

        tool_context.state["evaluation_metrics"] = metrics
        success_message("CriticTools", {"metrics": {key for key in metrics}})
        return metrics

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

        if not metrics or not isinstance(metrics, dict):
            metrics = self.get_evaluation_metrics(tool_context)

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
        code_zip = tool_context.state.get("finish_code_zip_base64") or tool_context.state.get("generated_code_zip")
        
        # Check if the generated code zip is in the session
        if not code_zip:
            error_message("CriticTools", "No generated_code_zip in session for syntax/executable scoring")
            return {
                "status": "error",
                "message": "No generated code zip in session. Run generate_code first.",
            }

        # Get the code coverage graph from the session
        raw_graph = tool_context.state.get("code_coverage_graph")
        code_coverage_graph = canonicalize_coverage_graph(raw_graph) if isinstance(raw_graph, dict) else None

        # Evaluate based on metrics
        coverage_scores = self._graph_coverage_score(opl_id, code_coverage_graph, tool_context)
        syntax_scores = self._syntax_and_executable_score(code_zip)

        # Calculate the overall score
        final_cvg_score = coverage_scores["overall_score"]
        final_syntax_and_exec_score = syntax_scores["overall_score"]
        overall_score = round((final_cvg_score * graph_weight + final_syntax_and_exec_score * exec_syntax_weight) / total_weight, 2)

        # Create final evaluation
        evaluation = {
            "graph_coverage": {
                "score": final_cvg_score,
                "breakdown": coverage_scores
            },
            "syntax_and_executable": {
                "score": final_syntax_and_exec_score,
                "breakdown": syntax_scores
            },
            "overall_score": overall_score,
        }

        # Save the evaluation scores to the database
        response = self._db.save_opl_evaluation_scores(opl_id, evaluation)
        if response.get("status") != "success":
            error_message("CriticTools", response.get("message"))
            return {"status": "error", "message": response.get("message")}

        tool_context.state["code_evaluation"] = evaluation
        success_message("CriticTools", {"evaluation": evaluation})
        return {"status": "success", "evaluation": evaluation}

    def adk_tools(self) -> list[Callable[..., Any]]:
        return [
            self.get_evaluation_metrics,
            self.generate_code_evaluation,
        ]