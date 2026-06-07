"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
        - index : Health check: ADK agent loads and Gemini API is reachable.
        - generate : Generate frontend/backend from OPL and download as a zip.
"""

import time
import uuid
from io import BytesIO
import base64
from flask import Blueprint, jsonify, request, send_file
from google.genai import types
from messages import error_message, start_message, success_message
from agent.agent import create_runner
from agent.opl_examples import demo2

from agent.health import check_agent_health
from agent.tools import is_valid_project_zip

agentAPI = Blueprint("agentAPI", __name__, url_prefix="/agent")
MAX_AGENT_ITERATIONS = 2
RETRIES = 3

@agentAPI.get("/")
def index():
    """
        Health check: ADK agent loads and Gemini API is reachable.
    """
    start_message("agent", "Health check")

    # Check the agent health
    try:
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
            opl: OPL source text (defaults to demo2)
            filename: download filename (defaults to agent-chosen project slug, or generated_code.zip)
    """
    start_message("agent", "Generate code zip")

    # Get the OPL and filename from the request
    filename = request.args.get("filename") or 'generated_project.zip'
    user_id = request.args.get("user_id") or "generate-api"
    opl_id = request.args.get("opl_id") or "6a2043546b3d44d88ccc7602"

    try:
        runner = create_runner(max_itr=MAX_AGENT_ITERATIONS, opl_id=opl_id)

        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text="Start workflow of given current_role"
                )
            ],
        )

        last_failure = "Failed to run the agent"
        run_length = 0

        for retry in range(RETRIES):
            print(f"Trying to run the agent : {retry + 1}/{RETRIES}")
            session_id = str(uuid.uuid4())

            runner.session_service.create_session_sync(
                app_name="model_based_codegen",
                user_id=user_id,
                session_id=session_id,
                state={
                    "current_role": "supervisor",
                    "initial_start": True,
                    "opl_id": opl_id,
                    "cnt_itr": 0,
                },
            )

            try:
                run_length = 0
                for _ in runner.run(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=message,
                ):
                    run_length += 1

                session = runner.session_service.get_session_sync(
                    app_name="model_based_codegen",
                    user_id=user_id,
                    session_id=session_id,
                )
                if not session:
                    last_failure = "Failed to load session after agent run"
                    error_message("agentAPI", f"{last_failure} on retry {retry + 1}/{RETRIES}")
                else:
                    generated_code_zip = session.state.get("generated_code_zip")
                    workflow_problem = session.state.get("workflow_problem")

                    if generated_code_zip:
                        try:
                            zip_bytes = base64.b64decode(generated_code_zip)
                            if is_valid_project_zip(zip_bytes):
                                zip_file = BytesIO(zip_bytes)
                                success_message(
                                    "agentAPI",
                                    f"Agent created {run_length} events on retry {retry + 1}, "
                                    f"for user {user_id} with project name {session.state.get('project_name')}",
                                )
                                return send_file(
                                    zip_file,
                                    mimetype="application/zip",
                                    as_attachment=True,
                                    download_name=filename,
                                )
                            last_failure = "Generated zip is missing frontend/ and backend/ folders"
                        except Exception:
                            last_failure = "Generated code zip is not valid base64"
                    elif workflow_problem:
                        last_failure = str(workflow_problem)
                    elif run_length == 0:
                        last_failure = "Agent produced no events"
                    else:
                        last_failure = "No generated code zip in session"

                    error_message(
                        "agentAPI",
                        f"{last_failure} on retry {retry + 1}/{RETRIES}",
                    )
            except Exception as exc:
                last_failure = f"Failed to run the agent: {exc}"
                error_message("agentAPI", f"{last_failure} on retry {retry + 1}/{RETRIES}")

            if retry < RETRIES - 1:
                time.sleep(3)

        error_message("agentAPI", f"Generate failed after {RETRIES} retries: {last_failure}")
        return jsonify({
            "success": False,
            "message": last_failure,
        }), 500
    except Exception as exc:
        error_message("agentAPI", f"Generate failed: {exc}")
        return jsonify({
            "success": False,
            "message": f"Agent creation failed: {exc}",
        }), 500

@agentAPI.get("/train")
def train():
    """
        Train the agent to generate a Logic Map
    """

    start_message("agent", "Train agent")

    # TODO: Train the agent to generate a Logic Map

    return jsonify({
        "success": True,
        "message": "Agent trained successfully",
    }), 200