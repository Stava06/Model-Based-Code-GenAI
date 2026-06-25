"""
    Agent Tools module for the agent
"""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from google.adk.tools import ToolContext
from agent.memory import DBconnection
from .supervisor import SupervisorTools
from .generator import GeneratorTools
from .critic import CriticTools

class AgentTools:
    """
        Full agent tools collection

        Includes:
            - set_current_role : Switch active role: supervisor, generator, or critic.
            - adk_tools : All tools for the singular agent (unique names, no duplicates).
    """

    def __init__(self, db: DBconnection | None = None):
        db = db or DBconnection.from_config()
        self._supervisor = SupervisorTools(db)
        self._generator = GeneratorTools(db)
        self._critic = CriticTools(db)

    def set_current_role(self, role: str, tool_context: ToolContext) -> dict[str, Any]:
        """
            Set the current role: supervisor, generator, or critic.

            params:
                - role: The role to set: supervisor, generator, or critic.
                - tool_context: The tool context

            returns:
                - dict[str, Any] : The result
        """

        allowed = {"supervisor", "generator", "critic"}
        if role not in allowed:
            return {
                "status": "error",
                "message": f"role must be one of {sorted(allowed)}",
            }

        if role == "supervisor":
            try:
                tool_context.state["cnt_itr"] = int(tool_context.state.get("cnt_itr") or 0) + 1
            except (TypeError, ValueError):
                tool_context.state["cnt_itr"] = 1

        tool_context.state["current_role"] = role
        return {
            "status": "success",
            "current_role": role,
            "cnt_itr": tool_context.state.get("cnt_itr"),
        }

    def adk_tools(self) -> list[Callable[..., Any]]:
        """
            Return all tools for the agent

            returns: 
                - list[Callable[..., Any]] : The list of tools
        """
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