"""
    Short-lived in-memory cache for generated project zips

    The SSE generate stream cannot return the binary zip on the same connection,
    so the finished zip is parked here under an unguessable id and fetched by a
    follow-up download request.

    Includes:
        - store_zip : Park a zip and return its download id
        - get_zip : Retrieve a zip by id and user, enforcing the TTL
"""

from __future__ import annotations

import time
import uuid
from threading import Lock
from typing import Any

# Time to live for a parked zip (seconds)
TTL_SECONDS = 15 * 60

ZIP_SCHEMA = {
    "zip_bytes": bytes,
    "filename": str,
    "user_id": str,
    "expires_at": float,
}
class ZIPCache:
    """
        Short-lived in-memory cache for generated project zips
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def _purge_expired(self, now: float) -> None:
        """
            Drop every entry whose TTL has elapsed
        """
        # Find all expired entries
        expired = []
        for key, entry in self._cache.items():
            if entry["expires_at"] <= now:
                expired.append(key)

        # Purge the expired entries
        for key in expired:
            self._cache.pop(key, None)


    def store_zip(self, zip_bytes: bytes, filename: str, user_id: str) -> str:
        """
            Store a generated zip

            params:
                - zip_bytes: The bytes of the generated zip
                - filename: The filename of the generated zip
                - user_id: The user id of the requesting user

            returns:
                - str: The download id of the generated zip
        """
        # Generate a unique download id
        download_id = str(uuid.uuid4())

        now = time.time()
        with self._lock:
            # Purge the expired entries
            self._purge_expired(now)

            # Store the zip in the cache
            save_zip = ZIP_SCHEMA.copy()
            save_zip["zip_bytes"] = zip_bytes
            save_zip["filename"] = filename
            save_zip["user_id"] = user_id
            save_zip["expires_at"] = now + TTL_SECONDS
            self._cache[download_id] = save_zip
        return download_id

    def get_zip(self, download_id: str, user_id: str) -> dict[str, Any] | None:
        """
            Retrieve a generated zip

            params:
                download_id: The download id of the generated zip
                user_id: The user id of the requesting user

            returns:
                - dict[str, Any] | None: The generated zip, if found and owned by the user
        """
        # Check if the download id is valid
        if not download_id:
            return None

        # Check if the user id is valid
        if not user_id:
            return None

        now = time.time()
        with self._lock:
            # Purge the expired entries
            self._purge_expired(now)

            # Retrieve the zip from the cache
            entry = self._cache.get(download_id)

            # Check if the zip is found and owned by the user
            if entry is None or entry["user_id"] != user_id:
                return None

            return {"zip_bytes": entry["zip_bytes"], "filename": entry["filename"]}
