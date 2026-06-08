"""
    Files API for the app server
    
    Includes:
        - filesAPI : Blueprint for the files API
"""

from bson import ObjectId
from flask import Blueprint, request
from flask import jsonify, current_app
from messages import start_message, success_message, error_message
from datetime import datetime

filesAPI = Blueprint("fileAPI", __name__, url_prefix="/file")


def _opl_collection():
    """Get the OPL collection from app extensions."""
    return current_app.extensions.get("opl_collection")


@filesAPI.get("/")
def index():
    """Health check for the files API."""
    start_message("filesAPI", "Index route")

    coll = _opl_collection()
    is_ready = coll is not None

    health_check = {
        "service": "files",
        "success": is_ready,
        "is_ready": is_ready,
        "count": coll.count_documents({}) if is_ready else 0,
    }

    success_message("filesAPI", f"Health check is {'OK' if is_ready else 'FAILED'}")
    return jsonify(health_check), 200 if is_ready else 503


@filesAPI.post("/save")
def save_opl_file():
    """Save an OPL file to the database."""
    start_message("filesAPI", "Save OPL file route")

    coll = _opl_collection()
    if coll is None:
        error_message("filesAPI", "Database not configured")
        return jsonify({"success": False, "message": "Database not configured"}), 503

    body = request.get_json(silent=True) or {}
    opl_file = body.get("opl") or request.args.get("opl")
    user_id = body.get("user_id") or request.args.get("user_id")
    file_name = body.get("file_name") or request.args.get("file_name") or ""

    if not opl_file:
        error_message("filesAPI", "No OPL file provided")
        return jsonify({"success": False, "message": "No OPL file provided"}), 400

    mongo_opl_object = {
        "file_name": file_name,
        "user_id": user_id,
        "opl_data": opl_file,
        "created_at": datetime.now(),
    }

    try:
        result = coll.insert_one(mongo_opl_object)
        success_message("filesAPI", "OPL file saved successfully")
        return jsonify({"success": True, "data": str(result.inserted_id)}), 200
    except Exception as e:
        error_message("filesAPI", f"Error saving OPL file: {e}")
        return jsonify({"success": False, "message": f"Error saving OPL file: {e}"}), 500


@filesAPI.get("/evaluation/<opl_id>")
def get_evaluation(opl_id: str):
    """Get evaluation scores for a saved OPL document."""
    start_message("filesAPI", f"Get evaluation for {opl_id}")

    coll = _opl_collection()
    if coll is None:
        return jsonify({"success": False, "message": "Database not configured"}), 503

    try:
        doc = coll.find_one({"_id": ObjectId(opl_id)})
    except Exception:
        doc = None

    if doc is None:
        return jsonify({"success": False, "message": "OPL not found"}), 404

    evaluation = {
        "overall_score": doc.get("overall_score"),
        "graph_coverage_score": doc.get("graph_coverage_score"),
        "syntax_score": doc.get("syntax_score"),
        "exec_score": doc.get("exec_score"),
        "file_name": doc.get("file_name"),
    }

    success_message("filesAPI", "Evaluation retrieved")
    return jsonify({"success": True, "data": evaluation}), 200
