"""
    Files API for the app server
    
    Includes:
        - filesAPI : Blueprint for the files API
"""

from flask import Blueprint, request
from flask import jsonify
from messages import start_message, success_message, error_message

# Create the agent API blueprint
filesAPI = Blueprint("fileAPI", __name__, url_prefix="/file")

# Error message for login
ERROR_GET_FILE_MSG = {
    'success': False,
    'message': None,
    'data': None,
}

@filesAPI.get("/")
def index():
    """
        Index page for the files API
    """
    start_message("files", "Index page")

    # TODO: Health check for the files API
    answer = {
        "service": "files",
        "message": "not implemented",
        "success": True,
    }

    success_message("files", "Index page loaded successfully")
    return jsonify(answer), 200

@filesAPI.get("/get")
def get_opl_file():
    """
        Get a file by id or all files from user (email or id)
    """

    start_message("files", {"action": "get_opl_file"})

    global ERROR_GET_FILE_MSG
    error_msg = ERROR_GET_FILE_MSG

    if not request.args:
        error_msg['message'] = "email or id is required"
        error_msg['email'] = True
        error_msg['id'] = True
        return jsonify(error_msg), 400

    # Get the email or id from the request
    email = request.args.get("email")
    id = request.args.get("id")

    # Check if the email is missing
    if not email:
        error_msg['email'] = True
        error_msg['message'] = "email is required"
        return jsonify(error_msg), 400

    # Check if the id is missing