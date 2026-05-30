"""
    MongoDB data access for agent tools (domain persistence).
"""

from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from config import CONFIG
from flask import current_app
from messages import error_message

class DBconnection:
    """MongoDB repository used by Code Generator, Evaluator, and Optimizer tools."""

    def __init__(self, db: Database | None = None):
        self._db = db

    def _code_collection(self):
        """
            Get the code collection
        """
        conn = current_app.extensions.get("code_collection")

        # Check if the database is configured
        if conn is None:
            error_message('code', "Database not configured")
            return None

        return conn

    @classmethod
    def from_config(cls) -> "DBconnection":
        uri = CONFIG["database"]["uri"]
        db_name = CONFIG["database"]["name"]
        if not uri or not db_name:
            return cls(db=None)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        return cls(db=client[db_name])

    def _not_ready(self) -> dict[str, Any]:
        return {"status": "error", "message": "MongoDB is not configured"}

    def get_training_opl(self) -> dict[str, Any]:
        """Load training OPL from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def get_user_opl(self) -> dict[str, Any]:
        """Load user-provided OPL from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def save_problem(self, problem: str | None = None) -> dict[str, Any]:
        """Persist a generated problem to MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def get_opl_file(self) -> dict[str, Any]:
        """Resolve OPL file content from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def retrieve_opl_logic_map(self) -> dict[str, Any]:
        """Build or load the OPL logic map from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def save_code(self, code: str | None = None) -> dict[str, Any]:
        """Persist generated code to MongoDB."""
        if self._db is None:
            return self._not_ready()

        code_conn = self._code_collection()
        if code_conn is None:
            return {"status": "error", "message": "Code collection not configured"}

        code_conn.insert_one({"code": code})
        return {"status": "success", "message": "Code saved successfully"}

    def get_opl_map(self) -> dict[str, Any]:
        """Load OPL map from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}

    def get_opl_pass(self) -> dict[str, Any]:
        """Load OPL pass data from MongoDB."""
        if self._db is None:
            return self._not_ready()
        return {"status": "not_implemented"}
