from pymongo import MongoClient
from config import CONFIG
from messages import start_message, success_message, error_message

def init_mongo(app):
    start_message('mongo')
    uri = CONFIG["database"]["uri"]
    db_name = CONFIG["database"]["name"]
    coll_name = CONFIG["database"]["user_collection"]

    if not uri or not db_name or not coll_name:
        error_message('mongo', "Database configuration is missing")
        app.extensions["users_collection"] = None
        return

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping") 
        db = client[db_name]
        app.extensions["users_collection"] = db[coll_name]
        success_message('mongo', "MongoDB initialized successfully")
        return
    except Exception as e:
        error_message('mongo', f"Error initializing MongoDB: {e}")
        app.extensions["users_collection"] = None
