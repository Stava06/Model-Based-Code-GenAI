"""
    MongoDB data access for agent tools (domain persistence).
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database

from config import CONFIG
from flask import current_app
from messages import error_message

class DBconnection:
    """MongoDB repository used by Code Generator, Evaluator, and Optimizer tools."""

    def __init__(self, db: Database | None = None):
        self._db = db

    def _opl_collection(self):
        """
            Get the OPL collection
        """
        if self._db is None:
            return None

        coll_name = CONFIG["database"]["opl_collection"]
        if not coll_name:
            return None

        return self._db.get_collection(coll_name)

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

    def get_opl(self, opl_id: str) -> str:
        """
        Get an OPL from MongoDB

        Parameters:
            - opl_id: The ID of the OPL

        Returns:
            - str : The OPL
        """

        opl_col = self._opl_collection()
        if opl_col is None:
            return {"status": "error", "message": "OPL collection not configured"}

        row = opl_col.find_one({"_id": ObjectId(opl_id)})
        if not row:
            return {"status": "error", "message": f"OPL not found: {opl_id}"}

        opl = row.get("opl_data")
        if not opl:
            return {"status": "error", "message": f"OPL document has no opl_data: {opl_id}"}

        return {"status": "success", "data": opl}

    def get_user_opl_array(self, user_id: str) -> list[str]:
        """
        Get all user OPLs from MongoDB

        Parameters:
            - user_id: The ID of the user

        Returns:
            - list[str] : User-provided OPL
        """
        
        opl_col = self._opl_collection()
        if opl_col is None:
            return {"status": "error", "message": "OPL collection not configured"}

        opl_arr = opl_col.find({"user_id": user_id})

        return {"status": "success", "data": opl_arr}

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
