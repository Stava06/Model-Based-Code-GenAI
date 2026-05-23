"""Agent package — Google ADK singular agent."""

from .agent import APP_NAME, build_agent, create_runner, root_agent

# Back-compat alias
build_agents = build_agent

__all__ = ["root_agent", "build_agent", "build_agents", "create_runner", "APP_NAME"]
