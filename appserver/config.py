import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.is_file():
    load_dotenv(_env_path)

CONFIG = {
    "database": {
        "uri": os.getenv("MONGO_URL"),
        "name": os.getenv("MONGO_DB"),
        "user_collection": os.getenv("MONGO_COLLECTION"),
    }
}
