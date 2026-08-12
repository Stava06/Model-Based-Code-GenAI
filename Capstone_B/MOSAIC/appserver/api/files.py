"""
    Files API for the app server
    
    Includes:
        - filesAPI : Blueprint for the files API
"""

from io import BytesIO

from bson import ObjectId
from flask import Blueprint, request
from flask import jsonify, current_app, send_file
from messages import start_message, success_message, error_message
from datetime import datetime
from services.project_launcher import launch_project_in_vscode

filesAPI = Blueprint("fileAPI", __name__, url_prefix="/file")

def _opl_collection():
    """Get the OPL collection from app extensions."""
    return current_app.extensions.get("opl_collection")


def _serialize_project_summary(doc: dict) -> dict:
    """JSON-safe project metadata without OPL body or zip bytes."""
    created_at = doc.get("created_at")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()

    return {
        "id": str(doc["_id"]),
        "file_name": doc.get("file_name") or "",
        "created_at": created_at,
        "overall_score": doc.get("overall_score"),
        "graph_coverage_score": doc.get("graph_coverage_score"),
        "syntax_score": doc.get("syntax_score"),
        "exec_score": doc.get("exec_score"),
        "has_generated_code": bool(doc.get("has_generated_code")),
    }


def _serialize_project(doc: dict) -> dict:
    """Convert a MongoDB OPL document to a JSON-safe project payload."""
    summary = _serialize_project_summary(doc)
    summary["opl_data"] = doc.get("opl_data") or ""
    return summary

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
    # Prefer an explicit JSON "opl" key (including null) over query-string fallback.
    if "opl" in body:
        opl_file = body.get("opl")
    else:
        opl_file = request.args.get("opl")
    if isinstance(opl_file, str):
        opl_file = opl_file.strip()

    user_id = body.get("user_id") or request.args.get("user_id")
    file_name = body.get("file_name") or request.args.get("file_name") or ""

    if opl_file is None or opl_file == "":
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

@filesAPI.get("/myprojects/<user_id>")
def get_my_projects(user_id: str):
    """Get paginated project summaries for a user (without OPL content)."""
    start_message("filesAPI", f"Get projects for user {user_id}")

    coll = _opl_collection()
    if coll is None:
        return jsonify({"success": False, "message": "Database not configured"}), 503

    try:
        skip = max(int(request.args.get("skip", 0)), 0)
        limit = min(max(int(request.args.get("limit", 20)), 1), 50)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid skip or limit"}), 400

    try:
        total = coll.count_documents({"user_id": user_id})
        files = list(
            coll.find(
                {"user_id": user_id},
                {
                    "file_name": 1,
                    "created_at": 1,
                    "overall_score": 1,
                    "graph_coverage_score": 1,
                    "syntax_score": 1,
                    "exec_score": 1,
                },
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
    except Exception:
        files = []
        total = 0

    if files:
        ids = [doc["_id"] for doc in files]
        with_code = {
            row["_id"]
            for row in coll.find(
                {"_id": {"$in": ids}, "generated_code": {"$exists": True, "$ne": None}},
                {"_id": 1},
            )
        }
        for doc in files:
            doc["has_generated_code"] = doc["_id"] in with_code

    projects = [_serialize_project_summary(doc) for doc in files]
    success_message("filesAPI", f"Retrieved {len(projects)} project(s)")
    return jsonify(
        {
            "success": True,
            "data": projects,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    ), 200


@filesAPI.get("/opl/<opl_id>")
def get_opl_content(opl_id: str):
    """Get OPL content for a single project."""
    start_message("filesAPI", f"Get OPL content for {opl_id}")

    coll = _opl_collection()
    if coll is None:
        return jsonify({"success": False, "message": "Database not configured"}), 503

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "user_id is required"}), 400

    try:
        doc = coll.find_one(
            {"_id": ObjectId(opl_id), "user_id": user_id},
            {"opl_data": 1},
        )
    except Exception:
        doc = None

    if doc is None:
        return jsonify({"success": False, "message": "Project not found"}), 404

    success_message("filesAPI", "OPL content retrieved")
    return jsonify({"success": True, "data": doc.get("opl_data") or ""}), 200


@filesAPI.get("/download/<opl_id>")
def download_generated_project(opl_id: str):
    """Download the stored generated project zip for an OPL document."""
    start_message("filesAPI", f"Download generated project for {opl_id}")

    coll = _opl_collection()
    if coll is None:
        return jsonify({"success": False, "message": "Database not configured"}), 503

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "user_id is required"}), 400

    try:
        doc = coll.find_one({"_id": ObjectId(opl_id), "user_id": user_id})
    except Exception:
        doc = None

    if doc is None:
        return jsonify({"success": False, "message": "Project not found"}), 404

    zip_bytes = doc.get("generated_code")
    if not zip_bytes:
        return jsonify({"success": False, "message": "No generated project available"}), 404

    file_name = doc.get("file_name") or "generated_project"
    if not file_name.lower().endswith(".zip"):
        file_name = file_name.rsplit(".", 1)[0] + ".zip" if "." in file_name else f"{file_name}.zip"

    success_message("filesAPI", f"Serving stored project zip for {opl_id}")
    return send_file(
        BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=file_name,
    )


@filesAPI.post("/launch/<opl_id>")
def launch_stored_project(opl_id: str):
    """Extract a stored generated project and open it in VS Code with dev servers."""
    start_message("filesAPI", f"Launch stored project in VS Code for {opl_id}")

    coll = _opl_collection()
    if coll is None:
        return jsonify({"success": False, "message": "Database not configured"}), 503

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id") or request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "user_id is required"}), 400

    try:
        doc = coll.find_one({"_id": ObjectId(opl_id), "user_id": user_id})
    except Exception:
        doc = None

    if doc is None:
        return jsonify({"success": False, "message": "Project not found"}), 404

    zip_bytes = doc.get("generated_code")
    if not zip_bytes:
        return jsonify({"success": False, "message": "No generated project available"}), 404

    file_name = doc.get("file_name") or "generated_project"
    if not file_name.lower().endswith(".zip"):
        file_name = file_name.rsplit(".", 1)[0] + ".zip" if "." in file_name else f"{file_name}.zip"

    try:
        result = launch_project_in_vscode(zip_bytes, file_name)
        success_message("filesAPI", f"Launched stored project at {result['extract_path']}")
        return jsonify({"success": True, "data": result}), 200
    except RuntimeError as exc:
        error_message("filesAPI", f"Launch failed: {exc}")
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        error_message("filesAPI", f"Launch failed: {exc}")
        return jsonify({"success": False, "message": str(exc)}), 500