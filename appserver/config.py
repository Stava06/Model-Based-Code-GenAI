import os

CONFIG = {
    "database": {
        'uri': os.getenv('MONGO_URL'),
        'name': os.getenv('MONGO_DB'),
        'user_collection': os.getenv('MONGO_COLLECTION')
    }
}