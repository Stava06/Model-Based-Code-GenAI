"""
    ADK tool groups: Code Generator, Code Evaluator, OPL Map Optimizer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from google.adk.tools import ToolContext

from memory import DBconnection


def _stub(message: str) -> dict[str, Any]:
    return {"status": "not_implemented", "message": message}


class CodeGeneratorTools:
    """Code Generator — generation and validation tools."""

    def __init__(self, db: DBconnection):
        self._db = db

    def get_opl_file(self) -> dict[str, Any]:
        """Resolve OPL file content from memory or MongoDB."""
        return self._db.get_opl_file()

    def retrieve_opl_logic_map(self) -> dict[str, Any]:
        """Build or load the logic map from OPL."""
        return self._db.retrieve_opl_logic_map()

    def generate_code(self) -> dict[str, Any]:
        """Produce code from the OPL logic map."""
        return _stub("generate_code")

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
        return self._db.get_training_opl()

    def get_user_opl(self) -> dict[str, Any]:
        """Resolve user-provided OPL."""
        return self._db.get_user_opl()

    def generate_problem(self) -> dict[str, Any]:
        """Build the final problem before finishing the run."""
        return self._logic.generate_problem()

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist the problem to MongoDB."""
        return self._db.save_problem(problem=problem)

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

    # Supervisor
    def get_training_opl(self) -> dict[str, Any]:
        """Load training OPL from MongoDB (training mode)."""
        return self._supervisor.get_training_opl()

    def get_user_opl(self) -> dict[str, Any]:
        """Resolve user-provided OPL."""
        return self._supervisor.get_user_opl()

    # Code Generator
    def get_opl_file(self) -> dict[str, Any]:
        """Resolve OPL file content from memory or MongoDB."""
        return self._generator.get_opl_file()

    def retrieve_opl_logic_map(self) -> dict[str, Any]:
        """Build or load the logic map from OPL."""
        return self._generator.retrieve_opl_logic_map()

    def generate_code(self) -> dict[str, Any]:
        """Produce code from the OPL logic map."""
        return self._generator.generate_code()

    def validate_code(self) -> dict[str, Any]:
        """Check generated code syntax and semantics."""
        return self._generator.validate_code()

    def save_code(self, code: str | None = None) -> dict[str, Any]:
        """Persist valid generated code to MongoDB."""
        return self._generator.save_code(code=code)

    # Code Evaluator
    def get_opl_map(self) -> dict[str, Any]:
        """Load OPL map from MongoDB."""
        return self._evaluator.get_opl_map()

    def get_evaluation_metrics(self) -> dict[str, Any]:
        """Fetch metrics for code evaluation."""
        return self._evaluator.get_evaluation_metrics()

    def generate_code_evaluation(self) -> dict[str, Any]:
        """Produce code-level evaluation results."""
        return self._evaluator.generate_code_evaluation()

    def get_pass_metrics(self) -> dict[str, Any]:
        """Fetch metrics for pass evaluation."""
        return self._evaluator.get_pass_metrics()

    def generate_pass_evaluation(self) -> dict[str, Any]:
        """Produce pass-level evaluation results."""
        return self._evaluator.generate_pass_evaluation()

    # OPL Map Optimizer
    def get_opl_pass(self) -> dict[str, Any]:
        """Load OPL pass data from MongoDB."""
        return self._optimizer.get_opl_pass()

    def check_code_passed(self) -> dict[str, Any]:
        """Determine whether code already passed."""
        return self._optimizer.check_code_passed()

    def mark_code_passed(self) -> dict[str, Any]:
        """Mark code as passed in MongoDB."""
        return self._optimizer.mark_code_passed()

    def get_opl_evaluation(self) -> dict[str, Any]:
        """Fetch evaluation data for optimization."""
        return self._optimizer.get_opl_evaluation()

    def get_opl_optimization(self) -> dict[str, Any]:
        """Fetch optimization suggestions."""
        return self._optimizer.get_opl_optimization()

    def optimize_opl_map(self) -> dict[str, Any]:
        """Apply optimization to the OPL map."""
        return self._optimizer.optimize_opl_map()

    # Shared
    def validate_opl_map(self) -> dict[str, Any]:
        """Check whether the OPL map is valid."""
        return self._evaluator.validate_opl_map()

    def generate_problem(self) -> dict[str, Any]:
        """Generate a problem report for the current workflow step."""
        return self._generator.generate_problem()

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist a problem report to MongoDB."""
        return self._supervisor.save_problem(problem=problem)

    def adk_tools(self) -> list[Callable[..., dict[str, Any]]]:
        return [
            self.set_current_role,
            self.get_training_opl,
            self.get_user_opl,
            self.get_opl_file,
            self.retrieve_opl_logic_map,
            self.generate_code,
            self.validate_code,
            self.save_code,
            self.get_opl_map,
            self.validate_opl_map,
            self.get_evaluation_metrics,
            self.generate_code_evaluation,
            self.get_pass_metrics,
            self.generate_pass_evaluation,
            self.get_opl_pass,
            self.check_code_passed,
            self.mark_code_passed,
            self.get_opl_evaluation,
            self.get_opl_optimization,
            self.optimize_opl_map,
            self.generate_problem,
            self.save_problem,
        ]
