"""
    Extract a generated project zip and open it in VS Code with dev servers.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

APPSERVER_ROOT = Path(__file__).resolve().parent.parent
LAUNCH_SCRIPT = APPSERVER_ROOT / "scripts" / "open-in-vscode.ps1"


def _sanitize_dir_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    return cleaned or "generated_project"


def _default_extract_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "CodeGenAI" / "projects"
    return Path.home() / "CodeGenAI" / "projects"


def launch_project_in_vscode(zip_bytes: bytes, filename: str) -> dict[str, str]:
    """
    Save zip bytes, extract to a workspace folder, and run the VS Code launcher script.

    Returns:
        dict with extract_path and message on success.

    Raises:
        RuntimeError: When launch is unsupported or the script fails.
    """
    if sys.platform != "win32":
        raise RuntimeError("Open in VS Code is only supported on Windows")

    if not LAUNCH_SCRIPT.is_file():
        raise RuntimeError(f"Launcher script not found: {LAUNCH_SCRIPT}")

    project_name = _sanitize_dir_name(Path(filename).stem)
    extract_path = _default_extract_root() / project_name
    extract_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(zip_bytes)
        zip_path = tmp.name

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(LAUNCH_SCRIPT),
                "-ZipPath",
                zip_path,
                "-ExtractPath",
                str(extract_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        try:
            os.unlink(zip_path)
        except OSError:
            pass

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "Unknown launcher error").strip()
        raise RuntimeError(details)

    message = (result.stdout or "Project opened in VS Code.").strip()
    return {
        "extract_path": str(extract_path),
        "message": message,
    }
