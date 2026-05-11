from pymongo import MongoClient
from .config import CONFIG

def init_mongo(app):
    client = MongoClient(CONFIG["database"]["uri"])
    db = client[CONFIG["database"]["name"]]
    app.extensions["users_collection"] = db[CONFIG["database"]["user_collection"]]