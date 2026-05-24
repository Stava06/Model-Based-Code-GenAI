"""
    ADK tool groups: Code Generator, Code Evaluator, OPL Map Optimizer.
"""
from __future__ import annotations
import json
import re
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from config import CONFIG
from .memory import DBconnection
from .opl_examples import demo1, demo2
from .logic_map_example import logic_map_example

def _stub(message: str) -> dict[str, Any]:
    return {"status": "not_implemented", "message": message}


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _codegen_prompt(opl_logic_map: dict[str, Any], opl: str) -> str:
    return f"""You are an expert software engineer implementing a system from an OPL (Object-Process Language) specification.

Use the OPL logic map as the ontology: objects, processes, and relations define the domain vocabulary and semantics. The OPL text is the concrete system specification—implement every object, state, process, agent/instrument link, and behavioral rule described there.

## OPL logic map (JSON)
{json.dumps(opl_logic_map, indent=2)}

## OPL specification
{opl.strip()}

## Requirements
- Produce complete, runnable Python 3 code that faithfully models the OPL.
- Map OPL objects to classes or data structures; processes to methods or functions; states and transitions as explicit logic.
- Preserve names and relationships from the OPL where practical.
- Include a small `if __name__ == "__main__":` demo or test harness when it helps show behavior.
- Do not include explanations, markdown, or prose—output only the source code.
"""


class CodeGeneratorTools:
    """Code Generator — generation and validation tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_file(self):
        """Resolve OPL file content from memory or MongoDB."""

        # TODO: Get opl from Local Storage

        return demo1

    def retrieve_opl_logic_map(self):
        """Build or load the logic map from OPL."""

        # TODO: Retrieve opl logic map from MongoDB

        return logic_map_example

    def generate_code(self, opl_logic_map: dict[str, Any], opl: str):
        """Produce code from the OPL logic map using Gemini API."""
        gemini = CONFIG["gemini"]
        api_key = gemini.get("api_key")
        model = gemini.get("model")

        if not api_key:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY is not configured",
            }

        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=_codegen_prompt(opl_logic_map, opl),
                config={"temperature": 0.2},
            )
            raw = getattr(response, "text", None) or ""
            code = _strip_code_fences(raw)
            if not code.strip():
                return {
                    "status": "error",
                    "message": "Gemini returned empty code",
                }
            return {"status": "success", "code": code}
        except ImportError:
            return {
                "status": "error",
                "message": "google-genai not installed (install google-adk)",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def validate_code(self) -> dict[str, Any]:
        """Check generated code syntax and semantics."""
        return _stub("validate_code")

    def save_code(self, code: str | None = None) -> dict[str, Any]:
        """Persist valid generated code to MongoDB."""
        return self._db.save_code(code=code)

    def generate_problem(self) -> dict[str, Any]:
        """Generate a problem report when generation fails or max attempts are reached."""
        return _stub("generate_problem")

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Save a problem report to MongoDB."""
        return self._db.save_problem(problem=problem)

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_opl_file,
            self.retrieve_opl_logic_map,
            self.generate_code,
            self.validate_code,
            self.save_code,
            self.generate_problem,
            self.save_problem,
        ]


class CodeEvaluatorTools:
    """Code Evaluator (Critic) — validation and evaluation tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_map(self) -> dict[str, Any]:
        """Load OPL map from MongoDB."""
        return self._db.get_opl_map()

    def validate_opl_map(self) -> dict[str, Any]:
        """Check whether the OPL map is valid."""
        return _stub("validate_opl_map")

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """Fetch metrics for code evaluation."""
        return _stub("get_evaluation_metrics")

    def generate_code_evaluation(self) -> dict[str, Any]:
        """Produce code-level evaluation results."""
        return _stub("generate_code_evaluation")

    def get_pass_metrics(self) -> dict[str, Any]:
        """Fetch metrics for pass evaluation."""
        return _stub("get_pass_metrics")

    def generate_pass_evaluation(self) -> dict[str, Any]:
        """Produce pass-level evaluation results."""
        return _stub("generate_pass_evaluation")

    def generate_problem(self) -> dict[str, Any]:
        """Build a problem report for an invalid OPL map."""
        return _stub("generate_problem")

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to MongoDB."""
        return self._db.save_problem(problem=problem)

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_opl_map,
            self.validate_opl_map,
            self.get_evaluation_metrics,
            self.generate_code_evaluation,
            self.get_pass_metrics,
            self.generate_pass_evaluation,
            self.generate_problem,
            self.save_problem,
        ]


class OPLMapOptimizerTools:
    """OPL Map Optimizer — optimization loop tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_pass(self) -> dict[str, Any]:
        """Load OPL pass data from MongoDB."""
        return self._db.get_opl_pass()

    def check_code_passed(self) -> dict[str, Any]:
        """Determine whether code already passed."""
        return _stub("check_code_passed")

    def mark_code_passed(self) -> dict[str, Any]:
        """Mark code as passed in MongoDB."""
        return _stub("mark_code_passed")

    def get_opl_evaluation(self) -> dict[str, Any]:
        """Fetch evaluation data for optimization."""
        return _stub("get_opl_evaluation")

    def get_opl_optimization(self) -> dict[str, Any]:
        """Fetch optimization suggestions."""
        return _stub("get_opl_optimization")

    def optimize_opl_map(self) -> dict[str, Any]:
        """Apply optimization to the OPL map."""
        return _stub("optimize_opl_map")

    def validate_opl_map(self) -> dict[str, Any]:
        """Check whether the optimized OPL map is valid."""
        return _stub("validate_opl_map")

    def generate_problem(self) -> dict[str, Any]:
        """Build a problem report when max optimization attempts are reached."""
        return _stub("generate_problem")

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to MongoDB."""
        return self._db.save_problem(problem=problem)

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_opl_pass,
            self.check_code_passed,
            self.mark_code_passed,
            self.get_opl_evaluation,
            self.get_opl_optimization,
            self.optimize_opl_map,
            self.validate_opl_map,
            self.generate_problem,
            self.save_problem,
        ]


class SupervisorTools:
    """Supervisor — OPL intake and finish tools."""

    def __init__(self, db: DBconnection, logic: CodeGeneratorTools):
        self._db = db
        self._logic = logic

    def get_training_opl(self) -> dict[str, Any]:
        """Load training OPL from MongoDB (training mode)."""

        # TODO: Get training OPL from MongoDB
        # TODO: Save opl to Local Storage

        return [demo1, demo2]

    def get_user_opl(self) -> dict[str, Any]:
        """Resolve user-provided OPL."""

        # TODO: Get user OPL from MongoDB
        # TODO: Save opl to Local Storage

        return demo1

    def generate_problem(self, message: str) -> dict[str, Any]:
        """Build the final problem before finishing the run."""

        # TODO: Generate problem

        return {
            "status": "failure",
            "message": message,
        }

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to MongoDB."""

        # TODO: Save problem to MongoDB

        return {
            "status": "success",
            "message": "Problem saved successfully",
        }

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_training_opl,
            self.get_user_opl,
            self.generate_problem,
            self.save_problem,
        ]


class AgentTools:
    """All tools for the singular agent (unique names, no duplicates)."""

    def __init__(self, db: DBconnection | None = None):
        db = db or DBconnection.from_config()
        self._generator = CodeGeneratorTools(db)
        self._evaluator = CodeEvaluatorTools(db)
        self._optimizer = OPLMapOptimizerTools(db)
        self._supervisor = SupervisorTools(db, self._generator)

    def set_current_role(self, role: str, tool_context: ToolContext) -> dict[str, Any]:
        """Switch active role: supervisor, generator, critic, or optimizer."""
        allowed = {"supervisor", "generator", "critic", "optimizer"}
        if role not in allowed:
            return {
                "status": "error",
                "message": f"role must be one of {sorted(allowed)}",
            }
        tool_context.state["current_role"] = role
        return {"status": "success", "current_role": role}

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        """
        Merge tool groups with unique names. Later groups with prefer=True win on conflicts.

        - validate_opl_map: Code Evaluator over Optimizer
        - generate_problem, save_problem: Supervisor over other groups
        """
        by_name: dict[str, Callable[..., dict[str, Any]]] = {}

        def add(fn: Callable[..., dict[str, Any]], *, prefer: bool = False) -> None:
            name = fn.__name__
            if prefer or name not in by_name:
                by_name[name] = fn

        for fn in self._optimizer.adk_tools():
            add(fn)
        for fn in self._evaluator.adk_tools():
            add(fn, prefer=True)
        for fn in self._generator.adk_tools():
            add(fn)
        for fn in self._supervisor.adk_tools():
            add(fn, prefer=True)

        return [self.set_current_role, *by_name.values()]
