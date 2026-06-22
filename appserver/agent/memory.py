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

    def _opl_logic_map_collection(self):
        """
        Get the OPL logic map collection
        """

        if self._db is None:
            return None

        coll_name = CONFIG["database"]["opl_logic_map_collection"]
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

    def get_latest_opl_logic_map(self) -> dict[str, Any]:
        """
        Get the OPL logic map from the database

        Parameters:
            - None

        Returns:
            - dict[str, Any] : The OPL logic map
        """

        opl_logic_map_col = self._opl_logic_map_collection()

        if opl_logic_map_col is None:
            return {"status": "error", "message": "OPL logic map collection not configured"}

        # Get the latest OPL logic map from the database
        latest_opl_logic_map = opl_logic_map_col.find_one(sort=[("created_at", -1)])
        
        if not latest_opl_logic_map:
            return {"status": "error", "message": "No OPL logic map found"}

        # Combine the OPL logic map into a single dictionary
        combined_logic_map = {
            "objects": latest_opl_logic_map.get("objects"),
            "processes": latest_opl_logic_map.get("processes"),
            "relations": latest_opl_logic_map.get("relations"),
        }

        return {"status": "success", "data": {"opl_logic_map": combined_logic_map, "created_at": latest_opl_logic_map.get("created_at")}}
    
    def save_opl_logic_map(self, opl_logic_map: dict[str, Any]) -> dict[str, Any]:
        """
        Save an OPL logic map to the database

        Parameters:
            - opl_logic_map : The OPL logic map (objects, processes, relations)

        Returns:
            - dict[str, Any] : The result
        """
        from datetime import datetime, timezone

        opl_logic_map_col = self._opl_logic_map_collection()
        if opl_logic_map_col is None:
            return {"status": "error", "message": "OPL logic map collection not configured"}

        if not isinstance(opl_logic_map, dict) or not opl_logic_map:
            return {"status": "error", "message": "opl_logic_map must be a non-empty object"}

        document = {
            "objects": opl_logic_map.get("objects"),
            "processes": opl_logic_map.get("processes"),
            "relations": opl_logic_map.get("relations"),
            "created_at": datetime.now(timezone.utc),
        }

        opl_logic_map_col.insert_one(document)
        return {"status": "success", "message": "OPL logic map saved to database"}

    def save_code_zip(self, code_zip: bytes, opl_id: str) -> dict[str, Any]:
        """
        Save the code zip to the database

        Parameters:
            - code_zip : The code zip
            - opl_id : The OPL ID

        Returns:
            - dict[str, Any] : The result
        """

        opl_col = self._opl_collection()
        if opl_col is None:
            return {"status": "error", "message": "OPL collection not configured"}

        opl_col.update_one({"_id": ObjectId(opl_id)}, {"$set": {"generated_code": code_zip}})
        return {"status": "success", "message": "Zip saved to database"}

    def save_opl_evaluation_scores(self, opl_id: str, eval: dict[str, Any]) -> dict[str, Any]:
        """
            Save the evaluation scores to the database

            Parameters:
                - opl_id : The OPL ID
                - eval : The evaluation scores

            Returns:
                - dict[str, Any] : The result
        """

        opl_col = self._opl_collection()
        if opl_col is None:
            return {"status": "error", "message": "OPL collection not configured"}

        graph_coverage_score = eval["graph_coverage"]["score"]
        syntax_score = eval["syntax_and_executable"]["breakdown"]["syntax_score"]
        executable_score = eval["syntax_and_executable"]["breakdown"]["executable_score"]
        overall_score = eval["overall_score"]

        opl_col.update_one({
            "_id": ObjectId(opl_id)}, 
            {"$set": {
                "graph_coverage_score": graph_coverage_score, 
                "syntax_score": syntax_score, 
                "exec_score": executable_score, 
                "overall_score": overall_score
            }
        })
        
        return {"status": "success", "message": "Graph coverage score saved to database"}