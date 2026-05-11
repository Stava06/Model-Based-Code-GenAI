from __future__ import annotations

from uuid import uuid4

from flask import Blueprint, jsonify, request, current_app

userAPI = Blueprint("userAPI", __name__, url_prefix="/users")
user_collection = current_app.extensions["users_collection"]

@userAPI.get("/")
def list_users():
    try:
        users = user_collection.find()
        return jsonify([user for user in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@userAPI.post("/create")
def create_user():
    try:
        user = {"name": "Stav Avraham", "email": "stav@gmail.com", "password": "123"}
        user_collection.insert_one(user)
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500