"""
    Users API for the app server
    
    Includes:
        - userAPI : Blueprint for the users API
        - _users_collection : Get the users collection
        - _serialize_user : Serialize a user document
        - _find_user : Find a user by email
        - list_users : List all users
        - login : Login a user
        - register : Register a user
        - get_user : Get a user by email
"""
from __future__ import annotations
from typing import Any
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

def _users_collection() -> dict:
    """
        Get the users collection

        returns:
            - conn: The connection to the users collection
    """
    conn = current_app.extensions.get("users_collection")

    # Check if the database is configured
    if conn is None:
        error_message('usersAPI', "Database not configured")

        # Set the error message
        ERROR_LOGIN_MSG['database'] = True
        ERROR_LOGIN_MSG['message'] = "Database not configured"

        return jsonify(ERROR_LOGIN_MSG), 503   

    return conn


def _serialize_user(user: dict) -> dict:
    """
        Serialize a user document

        params:
            - user: The user document

        returns:
            - user: The serialized user document
    """
    if "_id" in user:
        user["_id"] = str(user["_id"])
    return user

def _find_user(email: str) -> dict:
    """
        Find a user by email

        params:
            - email: The email of the user

        returns:
            - user: The user document
    """
    coll = _users_collection()
    
    try:
        # Find the user by email
        user = coll.find_one({"email": email})

        # Serialize the user and return it
        return _serialize_user(user) if user is not None else None
    except Exception as e:
        error_message('usersAPI', f"Error finding user: {e}")
        return None 

@userAPI.get("/")
def index():
    """
        Health check for the users API

        returns:
            - health_check: health check for the users API
    """
    start_message('usersAPI', "Index route")

    health_check = {
        "service": "users",
        "success": _users_collection() is not None,
        "is_ready": _users_collection() is not None,
        "count": _users_collection().count_documents({}) if _users_collection() is not None else 0,
    }

    success_message('usersAPI', f"Health check is {'OK' if health_check['success'] else 'FAILED'}")
    return jsonify(health_check), 200 if health_check['success'] else 503

@userAPI.get("/list")
def list():
    """
        List all users

        returns:
            - users: The list of users
    """
    start_message('usersAPI', "Listing users route")
    
    try:
        # Get the users collection
        coll = _users_collection()

        # Get all users and serialize them
        users = [_serialize_user(user) for user in coll.find()]

        success_message('usersAPI', "Users listed successfully")
        return jsonify(users), 200
    except Exception as e:
        error_message('usersAPI', f"Error listing users: {e}")
        return jsonify({"error": str(e)}), 500


@userAPI.get("/login")
def login():
    """
        Login a user by email and password

        params:
            - email: The email of the user
            - password: The password of the user

        returns:
            - answer: The answer to the login route
    """
    start_message("usersAPI", "Login route")

    global ERROR_LOGIN_MSG
    error_msg = ERROR_LOGIN_MSG.copy()

    # Check if the request has arguments
    if not request.args:
        error_message("usersAPI", "Email and password are required")
        error_msg["message"] = "Email and password are required"
        error_msg["email"] = True
        error_msg["password"] = True
        return jsonify(error_msg), 400

    # Get the email and password from the request
    email = request.args.get("email")
    password = request.args.get("password")

    # Check if the email is missing
    if not email:
        error_message("usersAPI", "Email was not provided")
        error_msg["email"] = True
        error_msg['message'] = "email is required"
        return jsonify(error_msg), 400

    # Check if the password is missing
    if not password:
        error_message("usersAPI", "Password was not provided")
        error_msg['password'] = True
        error_msg['message'] = "password is required"
        return jsonify(error_msg), 400

    try:
        # Find the user by email
        user = _find_user(email)

        # Check if the user is not found
        if user is None:
            error_message("usersAPI", "Email not registered")
            error_msg["message"] = "Email not registered"
            error_msg["email"] = True
            return jsonify(error_msg), 401

        # Check if the password is incorrect
        if user["password"] != password:
            error_message("usersAPI", "Incorrect password for given email")
            error_msg["message"] = "Incorrect password"
            error_msg["password"] = True
            return jsonify(error_msg), 401

        # Serialize the user and return the response
        data = _serialize_user(user)    

        success_message("usersAPI", f"User with email {email} logged in successfully")
        return jsonify({ "success": True, "message": "User logged in successfully", "data": data }), 200
    except Exception as e:
        error_message("usersAPI", f"Error logging in user: {e}")
        error_msg["message"] = str(e)
        return jsonify(error_msg), 500

@userAPI.post("/register")
def register():
    """
        Register a user by name, email and password

        params:
            - name: The name of the user
            - email: The email of the user
            - password: The password of the user

        returns:
            - answer: The answer to the register route
    """
    start_message("usersAPI", "Register route")

    global ERROR_REGISTER_MSG
    error_msg = ERROR_REGISTER_MSG.copy()

    # Check if the request has arguments
    if not request.json:
        error_message("usersAPI", "name, email, and password were not provided")
        error_msg["message"] = "name, email, and password are required"
        error_msg["name"] = True
        error_msg["email"] = True
        error_msg["password"] = True
        return jsonify(error_msg), 400

    # Get the name from the request
    name = request.json.get("name")
    if not name:
        error_message("usersAPI", "Name was not provided")
        error_msg["name"] = True
        error_msg["message"] = "name is required"
        return jsonify(error_msg), 400

    # Get the email from the request
    email = request.json.get("email")
    if not email:
        error_message("usersAPI", "Email was not provided")
        error_msg["email"] = True
        error_msg["message"] = "email is required"
        return jsonify(error_msg), 400
    
    # Get the password from the request
    password = request.json.get("password")
    if not password:
        error_message("usersAPI", "Password was not provided")
        error_msg["password"] = True
        error_msg["message"] = "password is required"
        return jsonify(error_msg), 400    

    # Check if the user is already registered
    check_user = _find_user(email)
    if check_user is not None:
        error_message("usersAPI", "Email already registered")
        error_msg["message"] = "Email already registered"
        error_msg["email"] = True
        return jsonify(error_msg), 400

    # Create the user
    user = {"name": name, "email": email, "password": password,}

    try:
        # Insert the user into the database
        _users_collection().insert_one(user)

        # Serialize the user and return the response
        data = _serialize_user(user)

        success_message("usersAPI", f"User with email {email} registered successfully")
        return jsonify({ "success": True, "message": "User registered successfully", "data": data }), 201
    except Exception as e:
        error_message("usersAPI", f"Error registering user: {e}")
        error_msg["message"] = str(e)
        return jsonify(error_msg), 500

@userAPI.get("/<string:email>")
def get_user(email: str):
    """
        Get a user by email

        params:
            - email: The email of the user

        returns:
            - answer: The answer to the get user route
    """
    start_message("usersAPI", "Get user route")
    
    # Find the user by email
    user = _find_user(email)

    # Check if the user is found
    if user is not None:
        # Serialize the user and return the response
        data = _serialize_user(user)

        success_message("usersAPI", f"User with email {email} retrieved successfully")
        return jsonify({ "success": True, "message": "User retrieved successfully", "data": data }), 200
    else:
        error_message("usersAPI", "User not found")
        return jsonify({ "success": False, "message": "User not found", "data": None }), 404
