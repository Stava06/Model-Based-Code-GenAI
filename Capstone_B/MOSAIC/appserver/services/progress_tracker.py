"""
    Generation progress tracking for the agent stream API

    Includes:
        - GenerationProgressTracker : Append-only activity log from ADK events
"""

from __future__ import annotations
import uuid
from typing import Any
from services.maps import STEP_MAP, TOOL_MAP, CRITICAL_SESSION_STATES

# Activity schema
ACTIVITY_SCHEMA: dict[str, Any] = {
    "id": str,
    "stepId": str,
    "label": str,
    "status": "active",
}

class GenerationProgressTracker:
    """
        Track generation as an append-only activity log.

        Each tool invocation adds a new row (even when the agent repeats the same
        action). Only one row is ``active`` at a time; starting a new activity
        marks the previous active row as ``done``.
    """

    def __init__(self) -> None:
        self._activities: list[dict[str, Any]] = []
        self._active_id: str | None = None

        self._start_activity("init")

    def _finish_activity(self) -> None:
        """
            Mark the current active activity as done
        """

        # Check if there is an active activity
        if not self._active_id:
            return

        # Find the active activity and mark it as done
        for activity in self._activities:
            if activity["id"] == self._active_id and activity["status"] == "active":
                activity["status"] = "done"
                break

        # Set the active id to None
        self._active_id = None

    def _start_activity(self, step_id: str, label: str | None = None) -> str:
        """
            Add a new activity to the list

            params:
                - step_id: The id of the step to add
                - label: The label of the step to add

            returns:
                - str : The id of the new activity
        """
        # Mark the current active activity as done
        self._finish_activity()

        if self._activities and self._activities[-1]["stepId"] == step_id:
            return self._activities[-1]["id"]
        
        # Add the new activity to the list
        activity_id = str(uuid.uuid4())

        activity = ACTIVITY_SCHEMA.copy()
        activity["id"] = activity_id
        activity["stepId"] = step_id
        activity["label"] = label or STEP_MAP.get(step_id, {}).get("label")

        self._activities.append(activity)
        self._active_id = activity_id

        return activity_id

    def _complete_latest_activity(self, step_id: str) -> bool:
        """
            Mark the recent activity for the given step id as done

            params:
                - step_id: The id of the step to mark as done

            returns:
                - bool : True if the activity was marked as done, False otherwise
        """
        changed = False
        for i in range(len(self._activities) - 1, -1, -1):
            curr_activity = self._activities[i]

            # Check if the current activity is the one we want to mark as done
            if curr_activity["stepId"] == step_id and curr_activity["status"] == "active":
                curr_activity["status"] = "done"

                # Set activity as done
                if self._active_id == curr_activity["id"]:
                    self._active_id = None

                changed = True
                break

        return changed

    def record_retry(self, attempt: int, max_attempts: int) -> None:
        """
            Record a retry attempt

            params:
                - attempt: The attempt number
                - max_attempts: The maximum number of attempts

        """
        self._start_activity("retry", f"Retrying generation (attempt {attempt}/{max_attempts})")

    def observe_event(self, event: Any) -> bool:
        """
            Observe an event and update the progress tracker

            params:
                - event: The event to observe

            returns:
                - bool : True if the event was observed, False otherwise
        """
        # Event tools called and their responses
        tools_called: set[str] = set()
        response_received: set[str] = set()
        session_states: dict[str, Any] = {}

        # Receive from the event the tools used with their responses
        try:
            tools_called = {fc.name for fc in event.get_function_calls()}
        except Exception:
            pass

        try:
            response_received = {fr.name for fr in event.get_function_responses()}
        except Exception:
            pass

        try:
            session_states = event.actions.state_delta or {}
        except Exception:
            pass

        # Create new activities for the tools called
        changed = False
        for tool_name in tools_called:
            step_id = TOOL_MAP.get(tool_name)
            if step_id:
                self._start_activity(step_id)
                changed = True

        # Update activities completed
        for tool_name in response_received:
            step_id = TOOL_MAP.get(tool_name)
            if step_id and self._complete_latest_activity(step_id):
                changed = True

        # Safeguard for changing session states
        for state_key in session_states:
            step_id = CRITICAL_SESSION_STATES.get(state_key)
            if step_id and self._complete_latest_activity(step_id):
                changed = True

        return changed

    def mark_packaging_done(self) -> None:
        """
            Mark the packaging activity as done
        """
        self._start_activity("packaging")
        self._finish_activity()

    @property
    def message(self) -> str:
        """
            Get the message for the current activity

            returns:
                - str : The message for the current activity
        """
        # Return the label of the current active activity, if exists
        if self._active_id:
            for i in range(len(self._activities) - 1, -1, -1):
                curr_activity = self._activities[i]

                # Check if the current activity is the active activity
                if curr_activity["id"] == self._active_id:
                    return curr_activity["label"]

        # Return the label of the last activity, if any
        if self._activities:
            return self._activities[-1]["label"]
        
        # Return the label of the initial activity
        return STEP_MAP.get("init", {}).get("label")

    def to_event(self, event_type: str = "progress") -> dict[str, Any]:
        """
            Convert the progress tracker to an event

            params:
                - event_type: The type of event to convert to

            returns:
                - dict[str, Any] : The event
        """
        # Retrieve the step weights from the activities
        step_weights = {step_id: info["weight"] for step_id, info in STEP_MAP.items()}
        
        return {
            "type": event_type,
            "message": self.message,
            "activities": self._activities,
            "step_weights": step_weights,
        }
