"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
        - index : Health check: ADK agent loads and Gemini API is reachable.
        - generate : Stream generation progress over SSE, then a download id.
        - generate_download : Serve a previously generated zip by download id.
        - train : Train the agent to generate a Logic Map
"""

import time
import uuid
import json
from io import BytesIO
import base64
from collections.abc import Iterator
from flask import Blueprint, jsonify, request, send_file, Response, stream_with_context
from google.genai import types
from messages import error_message, info_message, start_message, success_message
from agent.agent import create_runner
import os
from typing import Any
import agent as agent_module
from extensions import gemini_api_health_check
from config import CONFIG
from services.progress_tracker import GenerationProgressTracker
from services.zip_cache import ZIPCache
from services.project_launcher import launch_project_in_vscode

# Create the agent API blueprint
agentAPI = Blueprint("agentAPI", __name__, url_prefix="/agent")

# Max iterations for the agent
MAX_AGENT_ITERATIONS = 10

# Max retries for the agent generation
RETRIES = 3

# ZIP cache
ZIP_CACHE = ZIPCache()

def _agent_health_check() -> dict[str, Any]:
    """
        Verify the ADK agent and runner can be constructed

        returns:
            - response: The response from the agent health check
    """
    try:
        agent_module.root_agent
        agent_module.create_runner()
        return {"success": True, "message": "Agent and runner can be constructed"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}

def _execute_generation(opl_id: str, user_id: str, filename: str) -> Iterator[dict[str, Any]]:
    """
        Run the agent and yield progress events for the SSE stream.

        Mirrors the retry/session loop of ``generate`` but, instead of returning
        the zip directly, observes each runner event to advance a progress
        checklist and parks the finished zip in the download cache.

        params:
            - opl_id: The OPL id to generate from
            - user_id: The requesting user
            - filename: The download filename for the finished zip

        yields:
            - dict[str, Any] : SSE payloads (progress | retry | done | error)
    """
    tracker = GenerationProgressTracker()
    yield tracker.to_event()

    try:
        runner = create_runner(max_itr=MAX_AGENT_ITERATIONS, opl_id=opl_id)

        message = types.Content(
            role="user",
            parts=[types.Part(text="Start workflow of given current_role")],
        )

        for retry in range(RETRIES):
            info_message("agentAPI", f"Trying to run the agent : {retry + 1}/{RETRIES}")

            # Record the retry attempt
            if retry > 0:
                tracker.record_retry(retry + 1, RETRIES)
                yield tracker.to_event()

            # Create a new session
            session_id = str(uuid.uuid4())
            runner.session_service.create_session_sync(
                app_name=CONFIG["gemini"]["app_name"],
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
                # Run the agent, advancing the checklist as events arrive
                run_length = 0
                for result in runner.run(user_id=user_id, session_id=session_id, new_message=message):
                    run_length += 1

                    # Observe the event and update the progress tracker
                    if tracker.observe_event(result):
                        yield tracker.to_event()

                # Get the session updated by the agent
                session = runner.session_service.get_session_sync(
                    app_name=CONFIG["gemini"]["app_name"],
                    user_id=user_id,
                    session_id=session_id,
                )

                if session:
                    generated_code_zip = session.state.get("generated_code_zip")
                    workflow_problem = session.state.get("workflow_problem")

                    if workflow_problem:
                        error_message("agentAPI", f"{workflow_problem}")
                        yield {"type": "error", "message": str(workflow_problem)}
                        return
                    elif generated_code_zip:
                        try:
                            zip_bytes = base64.b64decode(generated_code_zip)

                            project_name = session.state.get("project_name")
                            success_message(
                                "agentAPI",
                                f"Agent created {run_length} events on retry {retry + 1}, "
                                f"for user {user_id} with project name {project_name}",
                            )

                            # Mark the packaging activity as done
                            tracker.mark_packaging_done()
                            yield tracker.to_event()

                            download_id = ZIP_CACHE.store_zip(zip_bytes, filename, user_id)

                            # Create the done event and yield it
                            done = tracker.to_event(event_type="done")
                            done["download_id"] = download_id
                            done["filename"] = filename

                            info_message("agentAPI", f"Generation complete, download_id={download_id}")
                            yield done
                            return
                        except Exception as e:
                            error_message("agentAPI", f"{e}")
                    elif run_length == 0:
                        error_message("agentAPI", "Agent produced no events")
                    else:
                        error_message("agentAPI", "No generated code zip in session")
                else:
                    error_message("agentAPI", f"Failed to load session after agent run, on retry {retry + 1}/{RETRIES}")
            except Exception as e:
                error_message("agentAPI", f"Exception on retry {retry + 1}/{RETRIES} : {e}")

            # Sleep for 3 seconds for the next retry
            if retry < RETRIES - 1:
                time.sleep(3)

        message = f"Agent generation failed after {RETRIES} retries"
        error_message("agentAPI", message)
        yield {"type": "error", "message": message}
    except Exception as exc:
        message = f"Generate failed: {exc}"
        error_message("agentAPI", message)
        yield {"type": "error", "message": message}

@agentAPI.get("/")
def index():
    """
        Health check for the agent API

        returns:
            - health_check: health check for the agent API
    """
    start_message("agentAPI", "Index route")

    health_check = {
        "service": "agentAPI",
        "success": False,
        "api_key_exists": False,
        "api_key_valid": False,
        "agent_loaded": False,
        "agent_message": None,
        "message": None,
    }

    # Check the agent health
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
        health_check["api_key_exists"] = api_key is not None

        # Check the Gemini API
        response = gemini_api_health_check(api_key)
        if response["success"]:
            health_check["api_key_valid"] = True
            success_message("agentAPI", "Gemini API is reachable")
        else:
            health_check["message"] = response["message"]
            error_message("agentAPI", f"Gemini API is not reachable: {response['message']}")
        
    except Exception as exc:
        error_message("agentAPI", f"Health check failed: {exc}")
        health_check["message"] = str(exc)
    
    # Check the agent health
    agent_health = _agent_health_check()

    if agent_health["success"]:
        health_check["agent_loaded"] = True
        health_check["agent_message"] = agent_health["message"]
        success_message("agentAPI", "Agent is loaded")
    else:
        health_check["agent_message"] = agent_health["message"]
        error_message("agentAPI", f"Agent is not loaded: {agent_health['message']}")
    
    health_check["success"] = health_check["api_key_exists"] and health_check["api_key_valid"] and health_check["agent_loaded"]
    success_message("agentAPI", f"Health check is {'OK' if health_check['success'] else 'FAILED'}")
    return jsonify(health_check), 200 if health_check["success"] else 503

@agentAPI.get("/generate")
def generate():
    """
        Generate a project while streaming progress over Server-Sent Events.

        Query params (optional):
            opl_id: OPL id to generate from
            user_id: requesting user (scopes the download)
            filename: download filename for the finished zip

        The stream emits ``progress`` events as the agent works, a final ``done``
        event carrying a ``download_id`` (fetch via ``/generate/download/<id>``),
        or an ``error`` event on failure.
    """
    start_message("agentAPI", "Generate code zip")

    filename = request.args.get("filename") or 'generated_project.zip'
    user_id = request.args.get("user_id") or "generate-api"
    opl_id = request.args.get("opl_id") or "6a2043546b3d44d88ccc7602"

    def event_stream():
        for payload in _execute_generation(opl_id, user_id, filename):
            yield f"data: {json.dumps(payload)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "close",
        },
    )

@agentAPI.get("/generate/download")
def generate_download():
    """
        Retrieve a previously generated zip by its download id

        Query params:
            user_id: requesting user
            download_id: download id of the generated project
    """
    start_message("agentAPI", f"Download generated project")

    user_id = request.args.get("user_id")
    download_id = request.args.get("download_id")

    if not user_id:
        error_message("agentAPI", "Download request missing user_id")
        return jsonify({"success": False, "message": "user_id is required"}), 400

    if not download_id:
        error_message("agentAPI", "Download request missing download_id")
        return jsonify({"success": False, "message": "download_id is required"}), 400

    try:
        entry = ZIP_CACHE.get_zip(download_id, user_id)

        if entry is None:
            error_message("agentAPI", f"Download not found or expired: {download_id}")
            return jsonify({"success": False, "message": "Download not found or expired"}), 404

        zip_file = BytesIO(entry["zip_bytes"])

        success_message("agentAPI", f"Serving download {download_id}")
        return send_file(
            zip_file,
            mimetype="application/zip",
            as_attachment=True,
            download_name=entry["filename"],
        )
    except Exception as exc:
        error_message("agentAPI", f"Download failed: {exc}")
        return jsonify({"success": False, "message": str(exc)}), 500

@agentAPI.post("/launch")
def launch_project():
    """
        Extract a generated zip and open it in VS Code with frontend/backend terminals.

        JSON body or query params:
            user_id: requesting user
            download_id: cached download id from generation
    """
    start_message("agentAPI", "Launch project in VS Code")

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id") or request.args.get("user_id")
    download_id = body.get("download_id") or request.args.get("download_id")

    if not user_id:
        error_message("agentAPI", "Launch request missing user_id")
        return jsonify({"success": False, "message": "user_id is required"}), 400

    if not download_id:
        error_message("agentAPI", "Launch request missing download_id")
        return jsonify({"success": False, "message": "download_id is required"}), 400

    try:
        entry = ZIP_CACHE.get_zip(download_id, user_id)
        if entry is None:
            error_message("agentAPI", f"Launch failed, download not found or expired: {download_id}")
            return jsonify({"success": False, "message": "Download not found or expired"}), 404

        result = launch_project_in_vscode(entry["zip_bytes"], entry["filename"])
        success_message("agentAPI", f"Launched project at {result['extract_path']}")
        return jsonify({"success": True, "data": result}), 200
    except RuntimeError as exc:
        error_message("agentAPI", f"Launch failed: {exc}")
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        error_message("agentAPI", f"Launch failed: {exc}")
        return jsonify({"success": False, "message": str(exc)}), 500
