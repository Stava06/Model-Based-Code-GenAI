from __future__ import annotations

from flask import Blueprint, current_app, jsonify

userAPI = Blueprint("userAPI", __name__, url_prefix="/users")


def _users_collection():
    return current_app.extensions.get("users_collection")


def _serialize_user(doc):
    user = dict(doc)
    if "_id" in user:
        user["_id"] = str(user["_id"])
    return user


@userAPI.get("/")
def list_users():
    coll = _users_collection()
    if coll is None:
        return jsonify({"error": "Database not configured"}), 503
    try:
        users = [_serialize_user(user) for user in coll.find()]
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@userAPI.post("/create")
def create_user():
    coll = _users_collection()
    if coll is None:
        return jsonify({"error": "Database not configured"}), 503
    try:
        user = {"name": "Stav Avraham", "email": "stav@gmail.com", "password": "123"}
        result = coll.insert_one(user)
        return jsonify({"message": "User created successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
