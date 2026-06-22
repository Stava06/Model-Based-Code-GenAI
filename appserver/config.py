import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """
    Config loader for the app server (singleton).
    """
    # The configuration dictionary
    _config: dict | None = None

    def __new__(cls):
        """
        Create a new instance of the Config class
        """
        # Check if the configuration dictionary is not loaded
        if cls._config is None:
            cls._config = cls._load_config()
        return cls._config

    @classmethod
    def _load_config(cls):
        """
            Load the configuration from the .env file

            returns:
                - config: The configuration dictionary
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
                "opl_collection": os.getenv("MONGO_OPL_COLLECTION"),
                "opl_logic_map_collection": os.getenv("MONGO_OPL_LOGIC_MAP_COLLECTION"),
            },
            "server": {
                "port": os.getenv("PORT") or 5000,
                "debug": os.getenv("FLASK_DEBUG") or False,
                "agent_debug": 4,
                "agent_debug_types": {
                    0: "none",
                    1: "supervisor",
                    2: "generator",
                    3: "critic",
                    4: "all",
                },
            },
            "gemini": {
                "api_key": os.getenv("GEMINI_API_KEY"),
                "model": os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite",
                "app_name": os.getenv("GEMINI_APP_NAME") or "model_based_codegen",
            },
        }

CONFIG = Config()

