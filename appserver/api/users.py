"""
    Users API for the app server
    
    Includes:
        - userAPI : Blueprint for the users API
        - _users_collection : Get the users collection
        - _serialize_user : Serialize a user document
        - list_users : List all users
        - login : Login a user
        - register : Register a user
"""
from __future__ import annotations
from flask import Blueprint, current_app, jsonify, request
from messages import start_message, success_message, error_message

# Error message for login
ERROR_LOGIN_MSG = {
    'success': False,
    'database': False,
    'password': False,
    'email': False,
    'message': None,
}

# Error message for register
ERROR_REGISTER_MSG = {
    'success': False,
    'database': False,
    'name': False,
    'email': False,
    'password': False,
    'message': None,
}

# Create the users API blueprint
userAPI = Blueprint("userAPI", __name__, url_prefix="/users")

def _users_collection():
    """
        Get the users collection
    """
    conn = current_app.extensions.get("users_collection")

    # Check if the database is configured
    if conn is None:
        error_message('users', "Database not configured")

        # Set the error message
        ERROR_LOGIN_MSG['database'] = True
        ERROR_LOGIN_MSG['message'] = "Database not configured"

        return jsonify(ERROR_LOGIN_MSG), 503   

    # Return the users collection
    return conn


def _serialize_user(doc: dict) -> dict:
    """
        Serialize a user document
    """
    user = dict(doc)
    if "_id" in user:
        user["_id"] = str(user["_id"])
    return user

def _find_user(email: str) -> dict:
    """
        Find a user by email
    """
    coll = _users_collection()
    
    # Find the user by email
    user = coll.find_one({"email": email})

    # Return the user or None
    return _serialize_user(user) if user is not None else None

@userAPI.get("/")
def index():
    """
        Index page for the users API
    """
    start_message('users', "Index page")

    answer = {
        "service": "users",
        "message": "ok",
        "is_ready": _users_collection() is not None,
        "count": _users_collection().count_documents({}) if _users_collection() is not None else 0,
    }

    success_message('users', "Index page loaded successfully")
    return jsonify(answer), 200

@userAPI.get("/list")
def list():
    """
        List all users
    """
    start_message('users', "Listing users")

    # Get the users collection
    coll = _users_collection()

    try:
        # Get all users and serialize them
        users = [_serialize_user(user) for user in coll.find()]

        success_message('users', "Users listed successfully")
        return jsonify(users), 200
    except Exception as e:
        error_message('users', f"Error listing users: {e}")
        return jsonify({"error": str(e)}), 500


@userAPI.get("/login")
def login():
    """
        Login a user by email and password
    """
    start_message("users", {"action": "login"})

    global ERROR_LOGIN_MSG
    error_msg = ERROR_LOGIN_MSG

    # Check if the request has arguments
    if not request.args:
        error_msg['message'] = "email and password are required"
        error_msg['email'] = True
        error_msg['password'] = True
        return jsonify(error_msg), 400

    # Get the email and password from the request
    email = request.args.get("email")
    password = request.args.get("password")

    # Check if the email is missing
    if not email:
        error_message("users", "email is required")
        error_msg['email'] = True
        error_msg['message'] = "email is required"
        return jsonify(error_msg), 400

    # Check if the password is missing
    if not password:
        error_message("users", "password is required")
        error_msg['password'] = True
        error_msg['message'] = "password is required"
        return jsonify(error_msg), 400

    try:
        # Find the user by email
        user = _find_user(email)

        # Check if the user is not found
        if user is None:
            error_msg['message'] = "Email not registered"
            error_msg['email'] = True
            return jsonify(error_msg), 401

        # Check if the password is incorrect
        if user["password"] != password:
            error_msg['message'] = "Incorrect password"
            error_msg['password'] = True
            return jsonify(error_msg), 401

        # Set the success message
        msg = { "success": True, "message": "User logged in successfully", "data": _serialize_user(user) }

        # Serialize the user and return the response
        success_message("users", msg["message"])
        return jsonify(msg), 200
    except Exception as e:
        error_message("users", f"Error logging in user: {e}")
        error_msg['message'] = str(e)
        return jsonify(error_msg), 500

@userAPI.post("/register")
def register():
    """
        Register a user by name, email and password
    """
    start_message("users", {"action": "register"})

    global ERROR_REGISTER_MSG
    error_msg = ERROR_REGISTER_MSG

    # Check if the request has arguments
    if not request.json:
        error_msg['message'] = "name, email, and password are required"
        error_msg['name'] = True
        error_msg['email'] = True
        error_msg['password'] = True
        return jsonify(error_msg), 400

    # Get the name from the request
    name = request.json.get("name")
    if not name:
        error_msg['name'] = True
        error_msg['message'] = "name is required"
        return jsonify(error_msg), 400

    # Get the email from the request
    email = request.json.get("email")
    if not email:
        error_msg['email'] = True
        error_msg['message'] = "email is required"
        return jsonify(error_msg), 400
    
    # Get the password from the request
    password = request.json.get("password")
    if not password:
        error_msg['password'] = True
        error_msg['message'] = "password is required"
        return jsonify(error_msg), 400    

    check_user = _find_user(email)
    if check_user is not None:
        error_msg['message'] = "Email already registered"
        error_msg['email'] = True
        return jsonify(error_msg), 400

    # Create the user
    user = {
        "name": name,
        "email": email,
        "password": password,
    }

    try:
        # Insert the user into the database
        _users_collection().insert_one(user)

        msg = { "success": True, "message": "User registered successfully", "data": _serialize_user(user) }

        success_message("users", msg["message"])
        return jsonify(msg), 201
    except Exception as e:
        error_message("users", f"Error registering user: {e}")
        error_msg['message'] = str(e)
        return jsonify(error_msg), 500

@userAPI.get("/<string:email>")
def get_user(email: str):
    """
        Get a user by email
    """
    start_message("users", {"action": "get_user", "email": email})
    
    # Find the user by email
    user = _find_user(email)

    # Set the message and return the response
    msg = { "success": True, "message": "User retrieved successfully", "data": user }

    # Check if the user is not found
    if user is None:
        msg['success'] = False
        msg['message'] = "User not found"

        error_message("users", msg["message"])
        return jsonify(msg), 404
    else:
        success_message("users", msg["message"])
        return jsonify(msg), 200
