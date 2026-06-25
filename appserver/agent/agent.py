"""
    Agent module for the app server

    Includes:
        - build_agent : Build the agent with all tools and unified role instructions
        - create_runner : Create a runner with in-memory sessions
        - root_agent : Root agent for the app server
"""

from __future__ import annotations
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from .memory import DBconnection
from .roles import supervisor_role
from .tools.agent_tools import AgentTools
from config import CONFIG

def _build_agent(db: DBconnection | None = None, max_itr: int = 10, opl_id: str = None) -> Agent:
    """
        Build the singular ADK agent with all tools and unified role instructions

        params:
            - db: MongoDB access layer; created from config if omitted
            - max_itr: Supervisor iteration cap
            - opl_id: OPL ID for this run

        returns:
            - Agent : The ADK agent
    """
    # Create a new MongoDB access layer
    db = db or DBconnection.from_config()

    # Create a new agent tools instance
    tools = AgentTools(db)

    # Create the agent name based on the app name
    name = CONFIG["gemini"]["app_name"] + "_agent"

    return Agent(
        name=name,
        model=CONFIG["gemini"]["model"],
        instruction=supervisor_role(
            max_itr=max_itr,
            opl_id=opl_id,
        ),
        tools=tools.adk_tools(),
    )

def create_runner(db: DBconnection | None = None, max_itr: int = 10, opl_id: str = None) -> Runner:
    """
        Create an ADK Runner with in-memory sessions

        params:
            - db: MongoDB access layer; created from config if omitted
            - max_itr: Supervisor maximum iterations count
            - opl_id: OPL ID for this run

        returns:
            - Runner : The ADK runner
    """
    # Create a new ADK agent with the agent builder
    agent = _build_agent(db=db, max_itr=max_itr, opl_id=opl_id)

    # Create a new in-memory session service
    session_service = InMemorySessionService()

    return Runner(
        app_name=CONFIG["gemini"]["app_name"],
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

# ADK web / CLI entry point
root_agent = _build_agent()
