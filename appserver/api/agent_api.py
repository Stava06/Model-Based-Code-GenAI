"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
"""

import base64
import uuid
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from google.genai import types
from messages import error_message, start_message, success_message
from agent.agent import APP_NAME, create_runner
from agent.opl_examples import demo1
from agent.tools import get_project_zip_from_state, _is_valid_project_zip, zip_entry_names

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
        Generate frontend/backend from OPL and download as a zip.

        Query params (optional):
            opl: OPL source text (defaults to demo1)
            filename: download filename (default: generated_code.zip)
    """
    start_message("agent", "Generate code zip")

    opl = request.args.get("opl") or demo1
    filename = request.args.get("filename", "generated_code.zip")
    if not filename.lower().endswith(".zip"):
        filename = f"{filename}.zip"

    try:
        runner = create_runner(max_itr=1)
        user_id = "generate-api"
        session_id = str(uuid.uuid4())
        runner.session_service.create_session_sync(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={
                "current_role": "supervisor",
                "initial_start": True,
                "training_mode": False,
                "opl": opl,
            },
        )
        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Operational mode: get OPL, hand off to Generator, run generate_code "
                        "(fullstack: React frontend/ with src/service.js + axios, "
                        "Flask backend/ with CORS API routes, in a zip), "
                        "save_generated_code, then finish."
                    )
                )
            ],
        )
        for _event in runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            pass

        session = runner.session_service.get_session_sync(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if not session:
            return jsonify({
                "success": False,
                "message": "Agent session not found",
            }), 500

        zip_b64 = get_project_zip_from_state(session.state)
        if not zip_b64:
            return jsonify({
                "success": False,
                "message": (
                    "No valid project zip in session — ensure the agent completed "
                    "generate_code before finish"
                ),
            }), 500

        zip_bytes = base64.b64decode(zip_b64)
        if not _is_valid_project_zip(zip_bytes):
            return jsonify({
                "success": False,
                "message": "Agent zip is missing frontend/ and backend/ folder trees",
                "zip_entries": zip_entry_names(zip_bytes),
            }), 500

        success_message(
            "agent",
            f"Code zip ready ({len(zip_entry_names(zip_bytes))} entries)",
        )
        return send_file(
            BytesIO(zip_bytes),
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        error_message("agent", f"Generate failed: {exc}")
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 500
