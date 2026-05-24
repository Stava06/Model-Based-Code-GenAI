"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
"""

import sys
from pathlib import Path

from flask import Blueprint, jsonify
from flask import request
from messages import error_message, start_message, success_message

agentAPI = Blueprint("agentAPI", __name__, url_prefix="/agent")


@agentAPI.get("/")
def index():
    """
        Health check: ADK agent loads and Gemini API is reachable.
    """
    start_message("agent", "Health check")

    try:
        from agent.health import check_agent_health

        health = check_agent_health()
    except Exception as exc:
        error_message("agent", f"Health check failed: {exc}")
        return jsonify({
            "service": "agent",
            "success": False,
            "healthy": False,
            "message": str(exc),
        }), 503

    healthy = health["healthy"]
    answer = {
        "service": "agent",
        "success": healthy,
        "healthy": healthy,
        "checks": health["checks"],
    }

    if healthy:
        success_message("agent", "Agent healthy")
        return jsonify(answer), 200

    error_message("agent", f"Agent unhealthy: {health['checks']}")
    return jsonify(answer), 503


@agentAPI.get("/generate")
def generate():
    """
        Generate code from the OPL
    """

    # TODO: Generate code from the OPL

    return jsonify({"message": "Generated code"}), 200
    
@agentAPI.get("/example")
def example():
    """
        Get an example OPL
    """
    from agent.memory import DBconnection
    from agent.tools import CodeGeneratorTools
    from agent.logic_map_example import logic_map_example
    from agent.opl_examples import demo1

    tools = CodeGeneratorTools(DBconnection.from_config())
    return jsonify(tools.generate_code(logic_map_example, demo1)), 200
