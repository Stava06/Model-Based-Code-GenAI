import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """
    Config loader for the app server (singleton).

    Config() always returns the same configuration dict.
    Prefer importing CONFIG from this module.
    """
    _config = None

    def __new__(cls):
        """
        Create a new instance of the Config class
        """
        if cls._config is None:
            cls._config = cls._load_config()
        return cls._config

    @classmethod
    def _load_config(cls):
        """
        Load the configuration from the .env file
        """
        # Get the path to the .env file
        env_path = Path(__file__).resolve().parent / ".env"

        # Check if the .env file exists
        if env_path.is_file():
            load_dotenv(env_path)

        return {
            "database": {
                "uri": os.getenv("MONGO_URL"),
                "name": os.getenv("MONGO_DB"),
                "user_collection": os.getenv("MONGO_USER_COLLECTION"),
                "code_collection": os.getenv("MONGO_CODE_COLLECTION"),
            },
            "server": {
                "port": os.getenv("PORT") or 5000,
                "debug": os.getenv("FLASK_DEBUG") or False,
            },
            "gemini": {
                "api_key": os.getenv("GEMINI_API_KEY"),
                "model": os.getenv("GEMINI_MODEL") or "gemini-2.5-flash",
            },
        }


CONFIG = Config()

