"""
    Extensions module for the app server
    
    Includes:
        - init_mongo : Initialize the MongoDB extension
        - gemini_api_health_check : Check the Gemini API health
        - call_gemini : Call the Gemini API
"""
import time
from typing import Any
import os
from pymongo import MongoClient
from config import CONFIG
from messages import start_message, success_message, error_message, info_message
from google import genai
from requests.exceptions import HTTPError

# Gemini retries count
GEMINI_RETRIES = 3

def init_mongo(app) -> None:
    """
        Initialize the MongoDB extension

        params:
            - app: The Flask app instance
    """
    start_message('mongoDB', "Initializing MongoDB extension")

    # Try to connect to the database
    try:
        # Get the database configuration
        uri = CONFIG["database"]["uri"]
        db_name = CONFIG["database"]["name"]
        user_coll_name = CONFIG["database"]["user_collection"]
        opl_coll_name = CONFIG["database"]["opl_collection"]
        opl_logic_map_coll_name = CONFIG["database"]["opl_logic_map_collection"]

        # Create a new MongoDB client
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)

        # Set the 
        db = client[db_name]
        app.extensions["users_collection"] = db[user_coll_name]
        app.extensions["opl_collection"] = db[opl_coll_name]
        app.extensions["opl_logic_map_collection"] = db[opl_logic_map_coll_name]

        success_message('mongoDB', "MongoDB initialized successfully")
        return
    except Exception as e:
        error_message('mongoDB', f"Error initializing MongoDB: {e}")
        app.extensions["users_collection"] = None
        app.extensions["opl_collection"] = None
        app.extensions["opl_logic_map_collection"] = None

def gemini_api_health_check(api_key: str) -> dict[str, Any]:
    """
        Verify Gemini credentials and a minimal API call.

        params:
            - api_key: The API key to use for the Gemini API

        returns:
            - response: The response from the Gemini API
    """
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        return {"success": False, "message": "API key is not set"}

    try:
        # Create a new Gemini client
        client = genai.Client(api_key=api_key)

        # Generate a response from the Gemini API
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: ok",
            config={"max_output_tokens": 16},
        )

        # Get the response text
        text = getattr(response, "text", None) or ""

        return {"success": True, "is_valid": text == "ok"}
    except ImportError:
        return {"success": False, "message": "google-genai not installed (install google-adk)"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}

def call_gemini(prompt: str):
    """
        Call the Gemini API

        params:
            - prompt: The prompt to call the Gemini API with
    """
    start_message('gemini API', "Calling Gemini API", {"prompt_length": len(prompt)})
    
    try:
        # Get the Gemini configuration
        gemini = CONFIG["gemini"]
        api_key = gemini.get("api_key")
        model = gemini.get("model")

        # Check if the Gemini API key is configured
        if not api_key:
            error_message('gemini API', "GEMINI_API_KEY is not configured")
            return {"status": "error", "message": "GEMINI_API_KEY is not configured"}
        
        # Create a new Gemini client
        client = genai.Client(api_key=api_key)

        for i in range(GEMINI_RETRIES):
            try:
                # Gnerate response from the Gemini API
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"temperature": 0.2, "response_mime_type": "application/json"},
                )

                # Get the response text
                data = getattr(response, "text", None) or ""

                success_message("gemini API", f"Response generated: length of {len(data)} tokens in attempt {i + 1}")
                return {"status": "success", "data": data}
            except HTTPError as exc:
                # Check if the error is retryable based on the status code
                status_code = exc.response.status_code
                is_retryable = True if status_code in [503, 500, 429] else False

                error_message("gemini API", f"{status_code} Error (attempt {i + 1}/{GEMINI_RETRIES}) : {exc.response.text}")
                if not is_retryable or i == GEMINI_RETRIES - 1:
                    return {"status": "error", "message": "Failed to generate response from Gemini API"}
                time.sleep(3)
    except Exception as exc:
        error_message('gemini API', f"Error calling Gemini API: {exc}")
        return {"status": "error", "message": "Failed to generate response from Gemini API"}
