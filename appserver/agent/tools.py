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
from agent.examples.logic_map_example import logic_map_example
from agent.examples.eval_metrics_example import metrics_example
from agent.examples.eval_example import evaluation_example
from agent.examples.optimization_example import optimization_example
from messages import start_message, error_message, success_message

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

def _optimize_prompt(opl_map: dict[str, Any], optimization: list[str]) -> str:
    optimization_text = "\n".join(optimization)
    return f"""You are an expert software engineer optimizing an OPL (Object-Process Language) specification.

You MUST:
- Improve logic correctness
- Improve execution order
- Remove redundancy
- Add missing necessary steps
- Optimize according to evaluation metrics

## OPL map (JSON)
{json.dumps(opl_map, indent=2)}

## Optimization
{optimization_text}

## Requirements
- Return ONLY a valid optimized OPL map (same JSON structure style)
- Do NOT explain
- Do NOT add commentary
- Keep schema consistent
- Do NOT fabricate evaluation metrics
- Do NOT fabricate optimization suggestions
"""

class CodeGeneratorTools:
    """Code Generator — generation and validation tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_file(self):
        """Resolve OPL file content from memory or MongoDB."""
        start_message("CodeGeneratorTools", "get_opl_file")

        # TODO: Get opl from Local Storage

        success_message("CodeGeneratorTools", "get_opl_file")
        return demo1

    def generate_code(self, opl_logic_map: dict[str, Any], opl: str):
        """Produce code from the OPL logic map using Gemini API."""
        start_message("CodeGeneratorTools", "generate_code")

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

            success_message("CodeGeneratorTools", "generate_code")
            return {"status": "success", "code": code}
        except ImportError:
            error_message("CodeGeneratorTools", "generate_code")

            return {
                "status": "error",
                "message": "google-genai not installed (install google-adk)",
            }
        except Exception as exc:
            error_message("CodeGeneratorTools", "generate_code")
            
            return {"status": "error", "message": str(exc)}

    def validate_code(self, code: str) -> bool:
        """Check generated code syntax and semantics."""
        start_message("CodeGeneratorTools", "validate_code")

        # TODO: Validate code syntax and semantics

        success_message("CodeGeneratorTools", "validate_code")
        return True

    def save_code(self, code: str) -> bool:
        """Persist valid generated code to MongoDB."""
        start_message("CodeGeneratorTools", "save_code")

        # TODO: Save code to MongoDB

        success_message("CodeGeneratorTools", "save_code")
        return True

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_opl_file,
            self.generate_code,
            self.validate_code,
            self.save_code,
        ]


class CodeEvaluatorTools:
    """Code Evaluator (Critic) — validation and evaluation tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_map(self) -> dict[str, Any]:
        """Load OPL map from MongoDB."""
        start_message("CodeEvaluatorTools", "get_opl_map")
        
        # TODO: Get opl map from MongoDB

        success_message("CodeEvaluatorTools", "get_opl_map")
        return logic_map_example

    def validate_opl_map(self, opl_map: dict[str, Any]) -> bool:
        """Check whether the OPL map is valid."""
        start_message("CodeEvaluatorTools", "validate_opl_map")
        
        # TODO: Validate opl map

        success_message("CodeEvaluatorTools", "validate_opl_map")
        return True

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """Fetch metrics for code evaluation."""
        start_message("CodeEvaluatorTools", "get_evaluation_metrics")
        
        # TODO: Get evaluation metrics from MongoDB

        success_message("CodeEvaluatorTools", "get_evaluation_metrics")
        return metrics_example

    def generate_code_evaluation(self, code: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
        """Produce code-level evaluation results."""
        start_message("CodeEvaluatorTools", "generate_code_evaluation")
        
        # TODO: Eval with Judge0
        # TODO: Eval with graph coverage
        # TODO: Eval with code BLEU

        #judge0_eval = 100*metrics_example[0]["weight"]
        #graph_coverage_eval = 100*metrics_example[1]["weight"]
        #code_bleu_eval = 100*metrics_example[2]["weight"]

        overall_eval = evaluation_example

        success_message("CodeEvaluatorTools", "generate_code_evaluation")
        return {"status": "success", "evaluation": overall_eval}

    def get_pass_metrics(self) -> int:
        """Fetch metrics for pass evaluation."""
        start_message("CodeEvaluatorTools", "get_pass_metrics")
        
        # TODO: Get pass metrics from MongoDB
        
        success_message("CodeEvaluatorTools", "get_pass_metrics")
        return 90

    def generate_pass_evaluation(self, code_evaluation: dict[str, Any], pass_metrics: int) -> bool:
        """Produce pass-level evaluation results."""
        start_message("CodeEvaluatorTools", "generate_pass_evaluation")
        
        success_message("CodeEvaluatorTools", "generate_pass_evaluation")
        return code_evaluation["overall_score"] >= pass_metrics

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.get_opl_map,
            self.validate_opl_map,
            self.get_evaluation_metrics,
            self.generate_code_evaluation,
            self.get_pass_metrics,
            self.generate_pass_evaluation,
        ]


class OPLMapOptimizerTools:
    """OPL Map Optimizer — optimization loop tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def mark_code_passed(self, pass_evaluation: bool) -> bool:
        """Mark code as passed in MongoDB."""
        start_message("OPLMapOptimizerTools", "mark_code_passed")
        
        # TODO: Mark code as passed in MongoDB

        success_message("OPLMapOptimizerTools", "mark_code_passed")
        return pass_evaluation

    def get_opl_evaluation(self) -> dict[str, Any]:
        """Fetch evaluation data from MongoDB."""
        start_message("OPLMapOptimizerTools", "get_opl_evaluation")

        # TODO: Get evaluation data from MongoDB

        success_message("OPLMapOptimizerTools", "get_opl_evaluation")
        return evaluation_example

    def get_opl_optimization(self) -> list[str]:
        """Fetch optimization from Local Storage."""
        start_message("OPLMapOptimizerTools", "get_opl_optimization")
        
        # TODO: Get optimization from Local Storage

        success_message("OPLMapOptimizerTools", "get_opl_optimization")
        return optimization_example.copy()

    def optimize_opl_map(self, opl_map: dict[str, Any], optimization: list[str]) -> dict[str, Any]:
        """Apply optimization to the OPL map."""
        start_message("OPLMapOptimizerTools", "optimize_opl_map")
        
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
                contents=_optimize_prompt(opl_map, optimization),
                config={"temperature": 0.2},
            )
            raw = getattr(response, "text", None) or ""
            opl_map = json.loads(raw)
            if not opl_map:
                error_message("OPLMapOptimizerTools", "optimize_opl_map")

                return {
                    "status": "error",
                    "message": "Gemini returned empty opl map",
                }

            # TODO: Save optimized opl map to Local Storage

            success_message("OPLMapOptimizerTools", "optimize_opl_map")
            return {"status": "success", "opl_map": opl_map}
        except ImportError:
            error_message("OPLMapOptimizerTools", "optimize_opl_map")
            
            return {
                "status": "error",
                "message": "google-genai not installed (install google-adk)",
            }
        except Exception as exc:
            error_message("OPLMapOptimizerTools", "optimize_opl_map")
            
            return {"status": "error", "message": str(exc)}

    def validate_opl_map(self, opl_map: dict[str, Any]) -> bool:
        """Check whether the optimized OPL map is valid."""
        start_message("OPLMapOptimizerTools", "validate_opl_map")
        
        # TODO: Validate opl map

        success_message("OPLMapOptimizerTools", "validate_opl_map")
        return True

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.mark_code_passed,
            self.get_opl_evaluation,
            self.get_opl_optimization,
            self.optimize_opl_map,
            self.validate_opl_map,
        ]


class SupervisorTools:
    """Supervisor — OPL intake and finish tools."""

    def __init__(self, db: DBconnection, logic: CodeGeneratorTools):
        self._db = db
        self._logic = logic

    def get_training_opl(self) -> dict[str, Any]:
        """Load training OPL from MongoDB (training mode)."""
        start_message("SupervisorTools", "get_training_opl")
        
        # TODO: Get training OPL from MongoDB
        # TODO: Save opl to Local Storage

        success_message("SupervisorTools", "get_training_opl")
        return [demo1, demo2]

    def get_user_opl(self) -> dict[str, Any]:
        """Resolve user-provided OPL."""
        start_message("SupervisorTools", "get_user_opl")
        
        # TODO: Get user OPL from MongoDB
        # TODO: Save opl to Local Storage

        success_message("SupervisorTools", "get_user_opl")
        return demo1

    def generate_problem(self, message: str) -> dict[str, Any]:
        """Build the final problem before finishing the run."""
        start_message("SupervisorTools", "generate_problem")
        
        # TODO: Generate problem

        success_message("SupervisorTools", "generate_problem")
        return {
            "status": "failure",
            "message": message,
        }

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to MongoDB."""
        start_message("SupervisorTools", "save_problem")
        
        # TODO: Save problem to MongoDB

        success_message("SupervisorTools", "save_problem")
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
