"""
    Health checks for the ADK agent and Gemini API.
"""

from __future__ import annotations

import os
from typing import Any


def _gemini_api_key() -> str | None:
    return (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_GENAI_API_KEY")
    )


def check_agent_loaded() -> dict[str, Any]:
    """Verify the ADK agent and runner can be constructed."""
    import agent as agent_module

    root = agent_module.root_agent
    runner = agent_module.create_runner()
    tool_count = len(root.tools) if root.tools else 0

    return {
        "ok": True,
        "name": root.name,
        "model": str(root.model),
        "app_name": agent_module.APP_NAME,
        "tool_count": tool_count,
        "runner": runner is not None,
    }


def check_gemini_api() -> dict[str, Any]:
    """Verify Gemini credentials and a minimal API call."""
    api_key = _gemini_api_key()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        return {
            "ok": False,
            "message": "Set GOOGLE_API_KEY, GEMINI_API_KEY, or GOOGLE_GENAI_API_KEY",
        }

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: ok",
            config={"max_output_tokens": 16},
        )
        text = getattr(response, "text", None) or ""
        return {
            "ok": True,
            "model": model,
            "message": "Gemini API reachable",
            "sample": text[:80] if text else None,
        }
    except ImportError:
        return {
            "ok": False,
            "message": "google-genai not installed (install google-adk)",
        }
    except Exception as exc:
        return {"ok": False, "model": model, "error": str(exc)}


def check_agent_health() -> dict[str, Any]:
    """Run agent and Gemini health checks."""
    checks: dict[str, Any] = {}
    healthy = True

    for name, check_fn in (
        ("agent", check_agent_loaded),
        ("gemini", check_gemini_api),
    ):
        try:
            result = check_fn()
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        checks[name] = result
        if not result.get("ok"):
            healthy = False

    return {"healthy": healthy, "checks": checks}
