"""
    Files API for the app server
    
    Includes:
        - filesAPI : Blueprint for the files API
"""

from flask import Blueprint, request
from flask import jsonify, current_app
from messages import start_message, success_message, error_message

# Create the agent API blueprint
filesAPI = Blueprint("fileAPI", __name__, url_prefix="/file")

# Error message for get file
ERROR_GET_FILE_MSG = {
    'success': False,
    'message': None,
    'data': None,
}

def _files_collection() -> dict:
    """
        Get the files collection

        returns:
            - conn: The connection to the files collection
    """
    conn = current_app.extensions.get("files_collection")

    # Check if the database is configured
    if conn is None:
        error_message('filesAPI', "Database not configured")

        # Set the error message
        ERROR_GET_FILE_MSG['message'] = "Database not configured"

        return jsonify(ERROR_GET_FILE_MSG), 503   

    return conn

@filesAPI.get("/")
def index():
    """
        Health check for the files API

        returns:
            - health_check: health check for the files API
    """
    start_message("filesAPI", "Index route")

    health_check = {
        "service": "files",
        "success": _files_collection() is not None,
        "is_ready": _files_collection() is not None,
        "count": _files_collection().count_documents({}) if _files_collection() is not None else 0,
    }

    success_message("filesAPI", f"Health check is {"OK" if health_check['success'] else "FAILED"}")
    return jsonify(health_check), 200 if health_check['success'] else 503


@filesAPI.get("/get")
def get_opl_file():
    """
        Get a file by id or all files from user (email or id)
        
        returns:
            - opl_file: The OPL file retrieved
    """
    start_message("filesAPI", "Get OPL file route")

    return jsonify({"message": "Not implemented"}), 501