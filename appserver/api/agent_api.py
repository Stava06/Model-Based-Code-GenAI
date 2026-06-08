"""
    Agent API for the app server

    Includes:
        - agentAPI : Blueprint for the agent API
        - index : Health check: ADK agent loads and Gemini API is reachable.
        - generate : Generate frontend/backend from OPL and download as a zip.
        - train : Train the agent to generate a Logic Map
"""

import time
import uuid
from io import BytesIO
import base64
from flask import Blueprint, jsonify, request, send_file
from google.genai import types
from messages import error_message, info_message, start_message, success_message
from agent.agent import create_runner
import os
from typing import Any
import agent as agent_module
from extensions import gemini_api_health_check
from config import CONFIG

# Create the agent API blueprint
agentAPI = Blueprint("agentAPI", __name__, url_prefix="/agent")

# Max iterations for the agent
MAX_AGENT_ITERATIONS = 2

# Max retries for the agent generation
RETRIES = 3

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
        Generate frontend/backend from OPL and download as a zip.

        Query params (optional):
            opl: OPL source text (defaults to demo2)
            filename: download filename (defaults to agent-chosen project slug, or generated_code.zip)
    """
    start_message("agentAPI", "Generate code zip")

    # Get request parameters from the query string
    filename = request.args.get("filename") or 'generated_project.zip'
    user_id = request.args.get("user_id") or "generate-api"
    opl_id = request.args.get("opl_id") or "6a2043546b3d44d88ccc7602"

    try:
        # Create a new runner
        runner = create_runner(max_itr=MAX_AGENT_ITERATIONS, opl_id=opl_id)

        message = types.Content(
            role="user",
            parts=[types.Part(text="Start workflow of given current_role")],
        )

        for retry in range(RETRIES):
            info_message("agentAPI", f"Trying to run the agent : {retry + 1}/{RETRIES}")

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
                # Run the agent and count the number of iterations
                run_length = 0
                for _ in runner.run(user_id=user_id, session_id=session_id, new_message=message):
                    run_length += 1

                # Get the session updated by the agent
                session = runner.session_service.get_session_sync(
                    app_name=CONFIG["gemini"]["app_name"],
                    user_id=user_id,
                    session_id=session_id,
                )

                # Check if the session is loaded
                if session:
                    # Get the generated code zip and workflow problem from the session
                    generated_code_zip = session.state.get("generated_code_zip")
                    workflow_problem = session.state.get("workflow_problem")

                    # Check if the generated code zip is valid
                    if generated_code_zip:
                        try:
                            # Decode the generated code zip from base64
                            zip_bytes = base64.b64decode(generated_code_zip)
                            zip_file = BytesIO(zip_bytes)

                            project_name = session.state.get("project_name")
                            message = f"Agent created {run_length} events on retry {retry + 1}, for user {user_id} with project name {project_name}"
                            success_message("agentAPI", message)
                            
                            # Send the generated code zip as a file
                            return send_file(
                                    zip_file,
                                    mimetype="application/zip",
                                    as_attachment=True,
                                    download_name=filename,
                            )
                        except Exception as e:
                            error_message("agentAPI", f"{e}")
                    elif workflow_problem:
                        error_message("agentAPI", f"{workflow_problem}")
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

        # Agent generation failed in all retries
        message = f"Agent generation failed after {RETRIES} retries"
        error_message("agentAPI", message)
        return jsonify({"success": False, "message": message,}), 500
    except Exception as exc:
        message = f"Generate failed: {exc}"
        error_message("agentAPI", message)
        return jsonify({"success": False, "message": message,}), 500

@agentAPI.get("/train")
def train():
    """
        Create a new logic map

        returns:
            - response: The response from the logic map creation
    """
    start_message("agentAPI", "Create a new logic map")

    # TODO: Train the agent to generate a Logic Map

    error_message("agentAPI", "Not implemented")
    return jsonify({"success": False, "message": "Not implemented"}), 500