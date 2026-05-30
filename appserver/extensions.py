"""
    Extensions module for the app server
    
    Includes:
        - init_mongo : Initialize the MongoDB extension
"""
from pymongo import MongoClient
from config import CONFIG
from messages import start_message, success_message, error_message

def init_mongo(app) -> None:
    """
        Initialize the MongoDB extension
    """
    start_message('mongo')

    # Get the database configuration
    uri = CONFIG["database"]["uri"]
    db_name = CONFIG["database"]["name"]
    user_coll_name = CONFIG["database"]["user_collection"]
    code_coll_name = CONFIG["database"]["code_collection"]

    # Check if the database configuration is missing
    if uri is None or db_name is None or user_coll_name is None:
        error_message('mongo', "Database configuration is missing")
        app.extensions["users_collection"] = None
        app.extensions["code_collection"] = None
        return

    # Try to connect to the database
    try:
        # Create a new MongoDB client
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)

        # Set the 
        db = client[db_name]
        app.extensions["users_collection"] = db[user_coll_name]
        app.extensions["code_collection"] = db[code_coll_name]

        success_message('mongo', "MongoDB initialized successfully")
        return
    except Exception as e:
        error_message('mongo', f"Error initializing MongoDB: {e}")
        app.extensions["users_collection"] = None
        app.extensions["code_collection"] = None