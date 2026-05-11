import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

CONFIG = {
    "database": {
        'uri': os.getenv('MONGO_URL'),
        'name': os.getenv('MONGO_DB'),
        'user_collection': os.getenv('MONGO_COLLECTION')
    }
}