from pymongo import MongoClient
from config import CONFIG


def init_mongo(app):
    uri = CONFIG["database"]["uri"]
    db_name = CONFIG["database"]["name"]
    coll_name = CONFIG["database"]["user_collection"]

    if not uri or not db_name or not coll_name:
        print("Database configuration is missing")
        app.extensions["users_collection"] = None
        return

    try:
        client = MongoClient(uri)
        db = client[db_name]
        app.extensions["users_collection"] = db[coll_name]
        print(f"MongoDB initialized successfully: {uri}")
    except Exception as e:
        print(f"Error initializing MongoDB: {e}")
        app.extensions["users_collection"] = None
