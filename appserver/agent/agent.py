"""
    Google ADK singular agent for model-based code generation.

    Architecture:
        LLM (Gemini) -> Roles (instruction + session.current_role) -> Tools -> Memory (MongoDB)

    One agent switches between Supervisor, Generator, and Critic behaviors
    via session.state and the unified instruction in roles.agent_instruction.

    Exports ``root_agent`` for ADK CLI / web discovery.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from .memory import DBconnection
from .roles import supervisor_role
from .tools import AgentTools

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def build_agent(
    db: DBconnection | None = None,
    *,
    max_itr: int = 10,
    opl_id: str = None,
) -> Agent:
    """
    Build the singular ADK agent with all tools and unified role instructions.

    Args:
        db: MongoDB access layer; created from config if omitted.
        max_itr: Supervisor iteration cap.
        opl_id: OPL ID for this run.
    """
    db = db or DBconnection.from_config()
    tools = AgentTools(db)

    return Agent(
        name="model_based_codegen_agent",
        model=DEFAULT_MODEL,
        instruction=supervisor_role(
            max_itr=max_itr,
            opl_id=opl_id,
        ),
        tools=tools.adk_tools(),
    )


def create_runner(
    db: DBconnection | None = None,
    *,
    max_itr: int = 10,
    opl_id: str = None,
) -> Runner:
    """Create an ADK Runner with in-memory sessions (swap for Mongo SessionService later)."""
    agent = build_agent(
        db=db,
        max_itr=max_itr,
        opl_id=opl_id,
    )
    session_service = InMemorySessionService()
    return Runner(
        app_name="model_based_codegen",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )


# ADK web / CLI entry point
root_agent = build_agent()
