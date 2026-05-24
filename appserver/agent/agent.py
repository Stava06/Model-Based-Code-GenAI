"""
    Google ADK singular agent for model-based code generation.

    Architecture:
        LLM (Gemini) -> Roles (instruction + session.current_role) -> Tools -> Memory (MongoDB)

    One agent switches between Supervisor, Generator, Critic, and Optimizer behaviors
    via session.state and the unified instruction in roles.agent_instruction.

    Exports ``root_agent`` for ADK CLI / web discovery.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from .memory import DBconnection
from .roles import agent_description, agent_instruction
from .tools import AgentTools

APP_NAME = "model_based_codegen"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def build_agent(
    db: DBconnection | None = None,
    *,
    max_itr: int = 10,
    max_gnr: int = 10,
    max_opt: int = 10,
    training_mode: bool = False,
) -> Agent:
    """
    Build the singular ADK agent with all tools and unified role instructions.

    Args:
        db: MongoDB access layer; created from config if omitted.
        max_itr: Supervisor iteration cap.
        max_gnr: Generator attempt cap.
        max_opt: Optimizer attempt cap.
        training_mode: Default training_mode in instructions.
    """
    db = db or DBconnection.from_config()
    tools = AgentTools(db)

    return Agent(
        name="model_based_codegen_agent",
        model=DEFAULT_MODEL,
        description=agent_description(),
        instruction=agent_instruction(
            max_itr=max_itr,
            max_gnr=max_gnr,
            max_opt=max_opt,
            training_mode=training_mode,
        ),
        tools=tools.adk_tools(),
    )


def create_runner(
    db: DBconnection | None = None,
    *,
    max_itr: int = 10,
    max_gnr: int = 10,
    max_opt: int = 10,
    training_mode: bool = False,
) -> Runner:
    """Create an ADK Runner with in-memory sessions (swap for Mongo SessionService later)."""
    agent = build_agent(
        db=db,
        max_itr=max_itr,
        max_gnr=max_gnr,
        max_opt=max_opt,
        training_mode=training_mode,
    )
    session_service = InMemorySessionService()
    return Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
    )


# ADK web / CLI entry point
root_agent = build_agent()
