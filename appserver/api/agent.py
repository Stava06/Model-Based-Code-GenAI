"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
"""

import uuid

from flask import Blueprint, jsonify
from flask import request
from google.genai import types
from messages import error_message, start_message, success_message
from agent.agent import create_runner
from agent.opl_examples import demo1

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
        Generate code from the OPL via the ADK runner.

        Query params (optional):
            opl: OPL source text (defaults to demo1)
            user_id: ADK session user id (default: api)
    """
    start_message("agent", "Generate code")

    opl = request.args.get("opl") or demo1
    user_id = request.args.get("user_id", "api")
    session_id = str(uuid.uuid4())

    new_message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Generate model-based code from this OPL:\n\n{opl}",
            ),
        ],
    )

    try:
        runner = create_runner()
        final_text = None
        event_count = 0
        for event in runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            event_count += 1
            if not event.is_final_response() or not event.content:
                continue
            parts = event.content.parts or []
            texts = [p.text for p in parts if p.text]
            if texts:
                final_text = "\n".join(texts)

        if event_count == 0:
            raise RuntimeError(
                "Agent run produced no events (check server logs for ADK errors)",
            )

        success_message("agent", "Code generated successfully")
        return jsonify({
            "success": True,
            "session_id": session_id,
            "response": final_text,
            "event_count": event_count,
        }), 200
    except Exception as exc:
        error_message("agent", f"Generate failed: {exc}")
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 500
