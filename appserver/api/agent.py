"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
"""

import sys
from pathlib import Path

from flask import Blueprint, jsonify

from messages import error_message, start_message, success_message

_APPSERVER_DIR = Path(__file__).resolve().parents[1]
_AGENT_DIR = _APPSERVER_DIR / "agent"

for _path in (_APPSERVER_DIR, _AGENT_DIR):
    _entry = str(_path)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

agentAPI = Blueprint("agentAPI", __name__, url_prefix="/agent")


@agentAPI.get("/")
def index():
    """
        Health check: ADK agent loads and Gemini API is reachable.
    """
    start_message("agent", "Health check")

    try:
        from health import check_agent_health

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
