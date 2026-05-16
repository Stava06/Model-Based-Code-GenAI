from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from messages import start_message, success_message, error_message

userAPI = Blueprint("userAPI", __name__, url_prefix="/users")


def _users_collection():
    return current_app.extensions.get("users_collection")


def _serialize_user(doc):
    user = dict(doc)
    if "_id" in user:
        user["_id"] = str(user["_id"])
    return user


@userAPI.get("", strict_slashes=False)
@userAPI.get("/", strict_slashes=False)
def list_users():
    start_message('users', "Listing users")

    coll = _users_collection()
    if coll is None:
        error_message('users', "Database not configured")
        return jsonify({"error": "Database not configured"}), 503
    try:
        users = [_serialize_user(user) for user in coll.find()]
        success_message('users', "Users listed successfully")
        return jsonify(users), 200
    except Exception as e:
        error_message('users', f"Error listing users: {e}")
        return jsonify({"error": str(e)}), 500


@userAPI.route("/login", methods=["GET", "POST"], strict_slashes=False)
def login():
    start_message("users", {"action": "login"})

    if request.method == "GET":
        email = request.args.get("email")
        password = request.args.get("password")
    else:
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        password = data.get("password")

    if not email or not password:
        error_message("users", "email and password are required")
        return jsonify({"error": "email and password are required"}), 400

    coll = _users_collection()
    if coll is None:
        error_message("users", "Database not configured")
        return jsonify({"error": "Database not configured"}), 503
    try:
        user = coll.find_one({"email": email})
        if user is None or user["password"] != password:
            error_message("users", "Invalid email or password")
            return jsonify({"error": "Invalid email or password"}), 401

        success_message("users", "User logged in successfully")
        return jsonify(_serialize_user(user)), 200
    except Exception as e:
        error_message("users", f"Error logging in user: {e}")
        return jsonify({"error": str(e)}), 500

@userAPI.route("/register", methods=["GET", "POST"], strict_slashes=False)
def register():
    start_message("users", {"action": "register"})

    if request.method == "GET":
        name = request.args.get("name")
        email = request.args.get("email")
        password = request.args.get("password")
    else:
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

    if not name or not email or not password:
        error_message("users", "name, email, and password are required")
        return jsonify({"error": "name, email, and password are required"}), 400

    coll = _users_collection()
    if coll is None:
        error_message("users", "Database not configured")
        return jsonify({"error": "Database not configured"}), 503
    try:
        if coll.find_one({"email": email}):
            error_message("users", "User already exists")
            return jsonify({"error": "User already exists"}), 400

        result = coll.insert_one({"name": name, "email": email, "password": password})
        success_message("users", "User registered successfully")
        return jsonify(
            {"message": "User registered successfully", "id": str(result.inserted_id)}
        ), 201
    except Exception as e:
        error_message("users", f"Error registering user: {e}")
        return jsonify({"error": str(e)}), 500