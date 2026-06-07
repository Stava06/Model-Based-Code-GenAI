"""
    Extensions module for the app server
    
    Includes:
        - init_mongo : Initialize the MongoDB extension
        - call_gemini : Call the Gemini API
"""
import time

from pymongo import MongoClient
from config import CONFIG
from messages import start_message, success_message, error_message
from google import genai

GEMINI_RETRIES = 3
GEMINI_RETRY_DELAY_SEC = 3

def init_mongo(app) -> None:
    """
        Initialize the MongoDB extension

        params:
            - app: The Flask app instance
    """
    start_message('mongo')

    # Get the database configuration
    uri = CONFIG["database"]["uri"]
    db_name = CONFIG["database"]["name"]
    user_coll_name = CONFIG["database"]["user_collection"]
    opl_coll_name = CONFIG["database"]["opl_collection"]
    opl_logic_map_coll_name = CONFIG["database"]["opl_logic_map_collection"]

    # Check if the database configuration is missing
    if uri is None or db_name is None or user_coll_name is None:
        error_message('mongo', "Database configuration is missing")
        app.extensions["users_collection"] = None
        app.extensions["opl_collection"] = None
        app.extensions["opl_logic_map_collection"] = None
        return

    # Try to connect to the database
    try:
        # Create a new MongoDB client
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)

        # Set the 
        db = client[db_name]
        app.extensions["users_collection"] = db[user_coll_name]
        app.extensions["opl_collection"] = db[opl_coll_name]
        app.extensions["opl_logic_map_collection"] = db[opl_logic_map_coll_name]

        success_message('mongo', "MongoDB initialized successfully")
        return
    except Exception as e:
        error_message('mongo', f"Error initializing MongoDB: {e}")
        app.extensions["users_collection"] = None
        app.extensions["opl_collection"] = None
        app.extensions["opl_logic_map_collection"] = None

def call_gemini(prompt: str):
    """
        Call the Gemini API

        params:
            - prompt: The prompt to call the Gemini API with
    """
    start_message('gemini', {"prompt_length": len(prompt)})
    
    # Get the Gemini configuration
    gemini = CONFIG["gemini"]
    api_key = gemini.get("api_key")
    model = gemini.get("model")

    # Check if the Gemini API key is configured
    if not api_key:
        error_message('gemini', "GEMINI_API_KEY is not configured")
        return {"status": "error", "message": "GEMINI_API_KEY is not configured"}
        
    client = genai.Client(api_key=api_key)
    last_error = "Error calling Gemini"

    for attempt in range(GEMINI_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "response_mime_type": "application/json"},
            )
            data = getattr(response, "text", None) or ""
            success_message("gemini", {"response_length": len(data), "attempt": attempt + 1})
            return {"status": "success", "data": data}
        except Exception as exc:
            last_error = f"Error calling Gemini: {exc}"
            retryable = any(
                marker in str(exc).upper()
                for marker in ("503", "500", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL")
            )
            error_message(
                "gemini",
                f"{last_error} (attempt {attempt + 1}/{GEMINI_RETRIES})",
            )
            if not retryable or attempt == GEMINI_RETRIES - 1:
                return {"status": "error", "message": last_error}
            time.sleep(GEMINI_RETRY_DELAY_SEC)

    return {"status": "error", "message": last_error}
