"""
MOSAIC live acceptance tests.

This module runs ten numbered checks against an already-running appserver:

    1. Full-Stack Code Generation      -> test_1_full_stack_code_generation
    2. Executable Generated Application-> test_2_executable_generated_application
    3. Requirement Coverage Evaluation -> test_3_requirement_coverage_evaluation
    4. End-to-End Generation Workflow  -> test_4_end_to_end_generation_workflow
    5. OPL Logic Map Generation        -> test_5_opl_logic_map_generation
    6. Login validity and edge cases   -> test_6_login_valid_and_edge_cases
    7. Null / empty OPL text rejection -> test_7_null_opl_text_rejected
    8. Register incomplete payloads    -> test_8_register_rejects_incomplete_payload
    9. Get user by email               -> test_9_get_user_by_email
   10. Save valid OPL + unknown eval   -> test_10_save_valid_opl_and_unknown_evaluation

Tests 1–5 run the full MOSAIC pipeline once and reuse the produced project.
Tests 6–10 are a lightweight ``MosaicApiUnitTest`` suite (no generation).

Only the Python standard library is used. Node.js/npm and the generated
backend's declared Python packages are treated as runtime prerequisites for the
executable check.

Prerequisites (the run uses REAL Gemini + MongoDB and may take several minutes):
    - The appserver is running and reachable at MOSAIC_BASE_URL.
    - MongoDB and a valid Gemini API key are configured for that server.
    - Node.js / npm are installed and on PATH (for the executable check).

Configuration (environment variables, all optional):
    MOSAIC_BASE_URL          Appserver base URL          (default http://localhost:5000)
    MOSAIC_USER_ID           User id for saved OPL/zip   (default acceptance-tester)
    MOSAIC_OPL_PATH          OPL file to upload          (default agent/opl_examples/demo1.opl)
    MOSAIC_FILENAME          Suggested zip filename      (default acceptance_project.zip)
    MOSAIC_HTTP_TIMEOUT      Per-request timeout (s)     (default 60)
    MOSAIC_SSE_TIMEOUT       Generation timeout (s)      (default 900)
    MOSAIC_APP_START_TIMEOUT Generated-app boot (s)      (default 300)
    MOSAIC_SKIP_LAUNCH       Skip the executable check   (default 0)

Single invocation (from the appserver directory):

    python tests/test_acceptance.py -v

or, using discovery:

    python -m unittest discover -s tests -p "test_acceptance.py" -v
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APPSERVER_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OPL = APPSERVER_ROOT / "agent" / "opl_examples" / "demo1.opl"

BASE_URL = os.environ.get("MOSAIC_BASE_URL", "http://localhost:5000").rstrip("/")
USER_ID = os.environ.get("MOSAIC_USER_ID", "acceptance-tester")
OPL_PATH = Path(os.environ.get("MOSAIC_OPL_PATH", str(DEFAULT_OPL)))
FILENAME = os.environ.get("MOSAIC_FILENAME", "acceptance_project.zip")

HTTP_TIMEOUT = int(os.environ.get("MOSAIC_HTTP_TIMEOUT", "60"))
SSE_TIMEOUT = int(os.environ.get("MOSAIC_SSE_TIMEOUT", "900"))
APP_START_TIMEOUT = int(os.environ.get("MOSAIC_APP_START_TIMEOUT", "300"))
SERVER_START_TIMEOUT = int(os.environ.get("MOSAIC_SERVER_START_TIMEOUT", "30"))
SKIP_LAUNCH = os.environ.get("MOSAIC_SKIP_LAUNCH", "0").lower() in ("1", "true", "yes")

LOGIN_EMAIL = os.environ.get("MOSAIC_LOGIN_EMAIL", "omri1@gmail.com")
LOGIN_PASSWORD = os.environ.get("MOSAIC_LOGIN_PASSWORD", "123456")
LOGIN_NAME = os.environ.get("MOSAIC_LOGIN_NAME", "Omri")

# Mandatory files expected in a generated fullstack project.
REQUIRED_FRONTEND_FILES = (
    "package.json",
    "index.html",
    "vite.config.js",
    "src/main.jsx",
    "src/App.jsx",
    "src/service.js",
)
REQUIRED_BACKEND_FILES = (
    "app.py",
    "requirements.txt",
)

# Ordered generation stages we expect to observe in the SSE activity log.
EXPECTED_STAGE_ORDER = (
    "building_logic_map",
    "generating",
    "evaluating",
)


# --------------------------------------------------------------------------- #
# HTTP helpers (standard library only)
# --------------------------------------------------------------------------- #

def _http_get_json(path: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
    """GET a URL and decode the JSON body. Returns (status, parsed_body)."""
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = exc.code
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


def _http_post_json(path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    """POST a JSON body and decode the JSON response. Returns (status, parsed_body)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = exc.code
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


def _http_get_bytes(path: str, params: dict[str, Any] | None = None) -> tuple[int, bytes, str]:
    """GET a binary body. Returns (status, content_bytes, content_type)."""
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")


def _consume_sse(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Open an SSE stream and collect every parsed ``data:`` payload until a
    terminal ``done``/``error`` event arrives or the stream closes.

    Raises AssertionError on transport failure so the shared setup fails loudly.
    """
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET", headers={"Accept": "text/event-stream"})

    events: list[dict[str, Any]] = []
    deadline = time.time() + SSE_TIMEOUT

    try:
        resp = urllib.request.urlopen(req, timeout=SSE_TIMEOUT)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise AssertionError(f"SSE request failed: HTTP {exc.code} {detail}") from exc
    except Exception as exc:  # noqa: BLE001 - surfaced as an assertion in setup
        raise AssertionError(f"SSE request failed: {exc}") from exc

    try:
        for raw in resp:
            if time.time() > deadline:
                raise AssertionError(
                    f"Generation exceeded MOSAIC_SSE_TIMEOUT ({SSE_TIMEOUT}s) "
                    f"after {len(events)} event(s)"
                )
            line = raw.decode("utf-8", "replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if not data:
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            events.append(payload)
            if payload.get("type") in ("done", "error"):
                break
    finally:
        resp.close()

    return events


# --------------------------------------------------------------------------- #
# Filesystem / project helpers
# --------------------------------------------------------------------------- #

def _find_project_root(extract_dir: Path) -> Path:
    """Return the directory that directly contains ``frontend`` and ``backend``."""
    if (extract_dir / "frontend").is_dir() and (extract_dir / "backend").is_dir():
        return extract_dir
    for child in extract_dir.iterdir():
        if child.is_dir() and (child / "frontend").is_dir() and (child / "backend").is_dir():
            return child
    return extract_dir


def _free_port() -> int:
    """Reserve and return an available localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _detect_flask_port(app_py: str) -> int | None:
    """Best-effort extraction of the port a generated Flask app binds to."""
    match = re.search(r"app\.run\([^)]*port\s*=\s*(\d+)", app_py)
    if match:
        return int(match.group(1))
    match = re.search(r"port\s*=\s*(\d+)", app_py)
    return int(match.group(1)) if match else None


def _first_get_route(app_py: str) -> str | None:
    """Find a parameterless GET route in a generated Flask app for a smoke call."""
    candidates: list[str] = []
    for match in re.finditer(r'@app\.get\(\s*["\']([^"\']+)["\']', app_py):
        candidates.append(match.group(1))
    for match in re.finditer(
        r'@app\.route\(\s*["\']([^"\']+)["\']([^)]*)\)', app_py
    ):
        route, rest = match.group(1), match.group(2)
        methods = re.search(r"methods\s*=\s*\[([^\]]*)\]", rest)
        if methods and "get" not in methods.group(1).lower():
            continue
        candidates.append(route)
    for route in candidates:
        if "<" not in route:  # skip routes with path params
            return route
    return None


def _wait_for_http(url: str, timeout: int) -> int | None:
    """Poll ``url`` until it responds (any status) or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code  # server is up and answering
        except Exception:  # noqa: BLE001 - not ready yet
            time.sleep(2)
    return None


# --------------------------------------------------------------------------- #
# Acceptance test case
# --------------------------------------------------------------------------- #

class MosaicAcceptanceTest(unittest.TestCase):
    """Runs the pipeline once in setUpClass and asserts across five checks."""

    opl_id: str = ""
    events: list[dict[str, Any]] = []
    activities: list[dict[str, Any]] = []
    done_event: dict[str, Any] | None = None
    zip_bytes: bytes = b""
    zip_content_type: str = ""
    extract_dir: Path | None = None
    project_root: Path | None = None
    evaluation: dict[str, Any] = {}
    _procs: list[subprocess.Popen] = []
    _log_files: list[Any] = []

    # ------------------------------------------------------------------ #
    # One-time live workflow
    # ------------------------------------------------------------------ #

    @classmethod
    def setUpClass(cls) -> None:
        cls._procs = []
        cls._log_files = []
        cls.addClassCleanup(cls._cleanup_resources)

        cls._ensure_appserver()
        cls._verify_health()

        opl_text = cls._read_opl()
        cls.opl_id = cls._save_opl(opl_text)

        cls.events = _consume_sse(
            "/agent/generate",
            {"opl_id": cls.opl_id, "user_id": USER_ID, "filename": FILENAME},
        )
        cls._resolve_terminal_event()

        cls.zip_bytes, cls.zip_content_type = cls._download_zip()
        cls._extract_zip()
        cls.evaluation = cls._fetch_evaluation()

    @classmethod
    def _ensure_appserver(cls) -> None:
        """Start the local appserver when the configured endpoint is unavailable."""
        try:
            _http_get_json("/")
            return
        except Exception:  # noqa: BLE001 - an unavailable server is handled below
            pass

        parsed_url = urllib.parse.urlparse(BASE_URL)
        if parsed_url.hostname not in {"localhost", "127.0.0.1"}:
            raise AssertionError(
                f"Appserver not reachable at {BASE_URL}. "
                "Automatic startup is only supported for localhost."
            )

        log_path = Path(tempfile.gettempdir()) / f"mosaic_appserver_{os.getpid()}.log"
        handle = open(log_path, "w+", encoding="utf-8", errors="replace")
        cls._log_files.append(handle)

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        proc = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=APPSERVER_ROOT,
            env=os.environ.copy(),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        proc._mosaic_log = log_path  # type: ignore[attr-defined]
        cls._procs.append(proc)

        if _wait_for_http(f"{BASE_URL}/", SERVER_START_TIMEOUT) is None:
            handle.flush()
            output = log_path.read_text(encoding="utf-8", errors="replace")
            raise AssertionError(
                f"Appserver did not start at {BASE_URL} within "
                f"{SERVER_START_TIMEOUT}s.\n--- appserver output ---\n{output}"
            )

    @classmethod
    def _verify_health(cls) -> None:
        try:
            root_status, _ = _http_get_json("/")
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                f"Appserver not reachable at {BASE_URL} ({exc}). "
                "Start it with `python app.py` and/or set MOSAIC_BASE_URL."
            ) from exc
        assert root_status == 200, f"Server health check failed: HTTP {root_status}"

        agent_status, agent_body = _http_get_json("/agent/")
        assert agent_status == 200, (
            f"Agent/Gemini not ready (HTTP {agent_status}): {agent_body}. "
            "Confirm GEMINI_API_KEY is configured."
        )

        file_status, file_body = _http_get_json("/file/")
        assert file_status == 200, (
            f"Files/MongoDB not ready (HTTP {file_status}): {file_body}. "
            "Confirm MONGO_URL is configured."
        )

    @classmethod
    def _read_opl(cls) -> str:
        assert OPL_PATH.is_file(), f"OPL file not found: {OPL_PATH}"
        text = OPL_PATH.read_text(encoding="utf-8")
        assert text.strip(), f"OPL file is empty: {OPL_PATH}"
        return text

    @classmethod
    def _save_opl(cls, opl_text: str) -> str:
        status, body = _http_post_json(
            "/file/save",
            {"opl": opl_text, "user_id": USER_ID, "file_name": OPL_PATH.name},
        )
        assert status == 200 and isinstance(body, dict) and body.get("success"), (
            f"Saving OPL failed (HTTP {status}): {body}"
        )
        opl_id = body.get("data")
        assert isinstance(opl_id, str) and opl_id, f"No opl_id returned: {body}"
        return opl_id

    @classmethod
    def _resolve_terminal_event(cls) -> None:
        assert cls.events, "Generation produced no SSE events"

        errors = [e for e in cls.events if e.get("type") == "error"]
        assert not errors, f"Generation reported an error: {errors[-1].get('message')}"

        done = [e for e in cls.events if e.get("type") == "done"]
        assert done, "Generation never emitted a terminal 'done' event"
        cls.done_event = done[-1]

        # The final activity log is carried on the last event that has one.
        for event in reversed(cls.events):
            if event.get("activities"):
                cls.activities = event["activities"]
                break

        assert cls.done_event.get("download_id"), "done event missing download_id"

    @classmethod
    def _download_zip(cls) -> tuple[bytes, str]:
        assert cls.done_event is not None
        status, content, content_type = _http_get_bytes(
            "/agent/generate/download",
            {"download_id": cls.done_event["download_id"], "user_id": USER_ID},
        )
        assert status == 200, f"Download failed (HTTP {status})"
        assert content, "Downloaded zip is empty"
        return content, content_type

    @classmethod
    def _extract_zip(cls) -> None:
        try:
            archive = zipfile.ZipFile(io.BytesIO(cls.zip_bytes))
        except zipfile.BadZipFile as exc:
            raise AssertionError(f"Downloaded content is not a valid zip: {exc}") from exc

        cls.extract_dir = Path(tempfile.mkdtemp(prefix="mosaic_acceptance_"))
        archive.extractall(cls.extract_dir)
        cls.project_root = _find_project_root(cls.extract_dir)

    @classmethod
    def _fetch_evaluation(cls) -> dict[str, Any]:
        status, body = _http_get_json(f"/file/evaluation/{cls.opl_id}")
        assert status == 200 and isinstance(body, dict) and body.get("success"), (
            f"Evaluation fetch failed (HTTP {status}): {body}"
        )
        data = body.get("data")
        assert isinstance(data, dict), f"Evaluation payload malformed: {body}"
        return data

    # ------------------------------------------------------------------ #
    # Cleanup
    # ------------------------------------------------------------------ #

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup_resources()

    @classmethod
    def _cleanup_resources(cls) -> None:
        for proc in cls._procs:
            cls._terminate(proc)
        cls._procs = []

        for handle in cls._log_files:
            try:
                handle.close()
            except Exception:  # noqa: BLE001
                pass
        cls._log_files = []

        if cls.extract_dir and cls.extract_dir.exists():
            # Give the OS a moment to release node/python file handles on Windows.
            time.sleep(1)
            shutil.rmtree(cls.extract_dir, ignore_errors=True)

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                proc.send_signal(subprocess.signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    # Acceptance test 1 - Full-Stack Code Generation
    # ------------------------------------------------------------------ #

    def test_1_full_stack_code_generation(self) -> None:
        """The system generates a complete full-stack project structure."""
        self.assertTrue(self.zip_bytes, "No project zip was generated")
        self.assertIsNotNone(self.project_root)
        root = self.project_root
        assert root is not None

        frontend = root / "frontend"
        backend = root / "backend"
        self.assertTrue(frontend.is_dir(), "Generated project missing frontend/ folder")
        self.assertTrue(backend.is_dir(), "Generated project missing backend/ folder")

        for rel in REQUIRED_FRONTEND_FILES:
            self.assertTrue(
                (frontend / rel).is_file(),
                f"Missing mandatory frontend file: frontend/{rel}",
            )
        for rel in REQUIRED_BACKEND_FILES:
            self.assertTrue(
                (backend / rel).is_file(),
                f"Missing mandatory backend file: backend/{rel}",
            )

        pkg = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        self.assertIn("react", deps, "frontend package.json missing react")
        self.assertIn("vite", deps, "frontend package.json missing vite")
        self.assertIn("axios", deps, "frontend package.json missing axios")

        app_py = (backend / "app.py").read_text(encoding="utf-8")
        self.assertIn("Flask", app_py, "backend app.py does not use Flask")
        self.assertRegex(
            app_py,
            r"from\s+flask_cors\s+import|import\s+flask_cors|CORS\s*\(",
            "backend app.py does not enable CORS",
        )

        service = (frontend / "src" / "service.js").read_text(encoding="utf-8")
        self.assertIn("axios", service, "frontend service.js does not use axios")

    # ------------------------------------------------------------------ #
    # Acceptance test 2 - Executable Generated Application
    # ------------------------------------------------------------------ #

    def test_2_executable_generated_application(self) -> None:
        """The generated app runs without manual code changes."""
        if SKIP_LAUNCH:
            self.skipTest("MOSAIC_SKIP_LAUNCH is set")

        npm = shutil.which("npm")
        if not npm:
            self.skipTest("npm not found on PATH; cannot launch the generated frontend")

        root = self.project_root
        assert root is not None
        frontend = root / "frontend"
        backend = root / "backend"

        backend_base = self._start_backend(backend)
        frontend_base = self._start_frontend(frontend, npm, backend_base)

        # Core functionality: the frontend serves and the backend answers a route.
        self.assertIsNotNone(
            _wait_for_http(frontend_base, 30),
            "Generated frontend did not serve any response",
        )

        app_py = (backend / "app.py").read_text(encoding="utf-8")
        route = _first_get_route(app_py) or "/"
        status = _wait_for_http(f"{backend_base}{route}", 30)
        self.assertIsNotNone(status, f"Generated backend route {route} was unreachable")
        assert status is not None
        self.assertLess(
            status, 500, f"Generated backend route {route} returned server error {status}"
        )

    def _start_backend(self, backend: Path) -> str:
        """Install deps and launch the generated Flask backend; return its base URL."""
        self._pip_install(backend / "requirements.txt", backend)

        app_py = (backend / "app.py").read_text(encoding="utf-8")
        detected = _detect_flask_port(app_py)
        env_port = _free_port()

        env = os.environ.copy()
        env["PORT"] = str(env_port)
        env["FLASK_RUN_PORT"] = str(env_port)

        proc = self._spawn(
            [sys.executable, "app.py"],
            cwd=backend,
            env=env,
            log_name="backend",
        )

        candidate_ports = [p for p in {detected, env_port} if p]
        deadline = time.time() + APP_START_TIMEOUT
        while time.time() < deadline:
            if proc.poll() is not None:
                self.fail(
                    "Generated backend process exited early.\n"
                    + self._proc_log("backend")
                )
            for port in candidate_ports:
                base = f"http://127.0.0.1:{port}"
                if _wait_for_http(base, 2) is not None:
                    return base
            time.sleep(2)

        self.fail(
            "Generated backend did not become reachable within "
            f"{APP_START_TIMEOUT}s on ports {candidate_ports}.\n"
            + self._proc_log("backend")
        )

    def _start_frontend(self, frontend: Path, npm: str, backend_base: str) -> str:
        """Install deps and launch the generated Vite dev server; return its base URL."""
        install = subprocess.run(
            [npm, "install"],
            cwd=str(frontend),
            capture_output=True,
            text=True,
            timeout=APP_START_TIMEOUT,
        )
        self.assertEqual(
            install.returncode,
            0,
            f"npm install failed for the generated frontend:\n{install.stderr or install.stdout}",
        )

        port = _free_port()
        env = os.environ.copy()
        env["VITE_API_URL"] = backend_base
        env["VITE_SERVER_URL"] = backend_base

        self._spawn(
            [npm, "run", "dev", "--", "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
            cwd=frontend,
            env=env,
            log_name="frontend",
        )

        base = f"http://127.0.0.1:{port}"
        status = _wait_for_http(base, APP_START_TIMEOUT)
        if status is None:
            self.fail(
                f"Generated frontend did not start on {base} within {APP_START_TIMEOUT}s.\n"
                + self._proc_log("frontend")
            )
        return base

    def _pip_install(self, requirements: Path, cwd: Path) -> None:
        if not requirements.is_file():
            return
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=APP_START_TIMEOUT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"pip install failed for the generated backend:\n{result.stderr or result.stdout}",
        )

    def _spawn(self, args: list[str], cwd: Path, env: dict[str, str], log_name: str) -> subprocess.Popen:
        log_path = Path(tempfile.gettempdir()) / f"mosaic_{log_name}_{os.getpid()}.log"
        handle = open(log_path, "w+", encoding="utf-8", errors="replace")
        type(self)._log_files.append(handle)

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        proc._mosaic_log = log_path  # type: ignore[attr-defined]
        type(self)._procs.append(proc)
        return proc

    def _proc_log(self, log_name: str) -> str:
        for proc in type(self)._procs:
            log_path = getattr(proc, "_mosaic_log", None)
            if log_path and log_name in Path(log_path).name:
                try:
                    return f"--- {log_name} output ---\n" + Path(log_path).read_text(
                        encoding="utf-8", errors="replace"
                    )
                except Exception:  # noqa: BLE001
                    return ""
        return ""

    # ------------------------------------------------------------------ #
    # Acceptance test 3 - Requirement Coverage Evaluation
    # ------------------------------------------------------------------ #

    def test_3_requirement_coverage_evaluation(self) -> None:
        """A coverage score and detailed evaluation metrics are produced."""
        expected_keys = (
            "overall_score",
            "graph_coverage_score",
            "syntax_score",
            "exec_score",
        )
        for key in expected_keys:
            self.assertIn(key, self.evaluation, f"Evaluation missing '{key}'")
            value = self.evaluation[key]
            self.assertIsNotNone(value, f"Evaluation '{key}' was not produced (None)")
            self.assertIsInstance(
                value, (int, float), f"Evaluation '{key}' is not numeric: {value!r}"
            )
            self.assertGreaterEqual(value, 0, f"Evaluation '{key}' below 0: {value}")
            self.assertLessEqual(value, 100, f"Evaluation '{key}' above 100: {value}")

    # ------------------------------------------------------------------ #
    # Acceptance test 4 - End-to-End Generation Workflow
    # ------------------------------------------------------------------ #

    def test_4_end_to_end_generation_workflow(self) -> None:
        """All roles complete: logic map, generation, evaluation, packaging, done."""
        self.assertIsNotNone(self.done_event, "Workflow never completed with 'done'")
        self.assertTrue(self.activities, "Workflow produced no activity log")

        step_order = self._first_seen_steps()

        for stage in EXPECTED_STAGE_ORDER:
            self.assertIn(
                stage,
                step_order,
                f"Workflow never reached stage '{stage}'. Observed: {step_order}",
            )

        # Supervisor -> Generator -> Critic manifests as this observable ordering.
        self._assert_subsequence(EXPECTED_STAGE_ORDER, step_order)

        # Packaging happens once the Generator's zip is finalized.
        self.assertIn(
            "packaging",
            step_order,
            f"Workflow never packaged the project. Observed: {step_order}",
        )
        self.assertEqual(
            self.done_event.get("filename"), FILENAME, "done event filename mismatch"
        )

    # ------------------------------------------------------------------ #
    # Acceptance test 5 - OPL Logic Map Generation
    # ------------------------------------------------------------------ #

    def test_5_opl_logic_map_generation(self) -> None:
        """A logic map is built and used before code generation."""
        step_order = self._first_seen_steps()

        self.assertIn(
            "building_logic_map",
            step_order,
            f"Logic map stage never ran. Observed: {step_order}",
        )
        self.assertIn(
            "generating",
            step_order,
            f"Code generation stage never ran. Observed: {step_order}",
        )
        self.assertLess(
            step_order.index("building_logic_map"),
            step_order.index("generating"),
            "Logic map was not built before code generation",
        )

        # The logic-map activity must have completed (been consumed by generation).
        logic_map_acts = [a for a in self.activities if a.get("stepId") == "building_logic_map"]
        self.assertTrue(logic_map_acts, "No logic-map activity recorded")
        self.assertTrue(
            any(a.get("status") == "done" for a in logic_map_acts),
            "Logic-map stage never reached 'done' status",
        )

        # And the map ultimately drove a produced artifact.
        self.assertTrue(self.zip_bytes, "Logic map did not lead to a generated project")

    # ------------------------------------------------------------------ #
    # Shared assertion helpers
    # ------------------------------------------------------------------ #

    def _first_seen_steps(self) -> list[str]:
        """Ordered, de-duplicated stepIds in the order they first appear."""
        seen: list[str] = []
        for activity in self.activities:
            step = activity.get("stepId")
            if step and step not in seen:
                seen.append(step)
        return seen

    def _assert_subsequence(self, expected: tuple[str, ...], observed: list[str]) -> None:
        positions = [observed.index(step) for step in expected if step in observed]
        self.assertEqual(
            positions,
            sorted(positions),
            f"Stages out of order. Expected {expected} within observed {observed}",
        )


# --------------------------------------------------------------------------- #
# Lightweight API unit tests (no code generation)
# --------------------------------------------------------------------------- #

class MosaicApiUnitTest(unittest.TestCase):
    """
    Fast HTTP checks against a running appserver.

    Does not run the agent pipeline. Starts the local appserver when needed,
    ensures the login fixture user exists, then exercises auth and file APIs.
    """

    _procs: list[subprocess.Popen] = []
    _log_files: list[Any] = []

    @classmethod
    def setUpClass(cls) -> None:
        cls._procs = []
        cls._log_files = []
        cls.addClassCleanup(cls._cleanup_resources)

        # Reuse the acceptance suite's local appserver bootstrap.
        MosaicAcceptanceTest._ensure_appserver.__func__(cls)

        try:
            root_status, _ = _http_get_json("/")
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                f"Appserver not reachable at {BASE_URL} ({exc}). "
                "Start it with `python app.py` and/or set MOSAIC_BASE_URL."
            ) from exc
        assert root_status == 200, f"Server health check failed: HTTP {root_status}"

        users_status, users_body = _http_get_json("/users/")
        assert users_status == 200, (
            f"Users/MongoDB not ready (HTTP {users_status}): {users_body}. "
            "Confirm MONGO_URL is configured."
        )

        file_status, file_body = _http_get_json("/file/")
        assert file_status == 200, (
            f"Files/MongoDB not ready (HTTP {file_status}): {file_body}. "
            "Confirm MONGO_URL is configured."
        )

        cls._ensure_login_user()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup_resources()

    @classmethod
    def _cleanup_resources(cls) -> None:
        for proc in cls._procs:
            MosaicAcceptanceTest._terminate(proc)
        cls._procs = []

        for handle in cls._log_files:
            try:
                handle.close()
            except Exception:  # noqa: BLE001
                pass
        cls._log_files = []

    @classmethod
    def _ensure_login_user(cls) -> None:
        """Register the fixture user, or reset password when the account already exists."""
        status, body = _http_post_json(
            "/users/register",
            {
                "name": LOGIN_NAME,
                "email": LOGIN_EMAIL,
                "password": LOGIN_PASSWORD,
            },
        )
        if status == 201 and isinstance(body, dict) and body.get("success"):
            return

        already_registered = status == 400 and isinstance(body, dict) and body.get("email")
        if not already_registered:
            raise AssertionError(
                f"Could not ensure login fixture user {LOGIN_EMAIL!r} "
                f"(HTTP {status}): {body}"
            )

        # Account exists — align password to the fixture so login edge cases are stable.
        login_status, login_body = _http_get_json(
            "/users/login",
            {"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        )
        if login_status == 200 and isinstance(login_body, dict) and login_body.get("success"):
            return

        try:
            from config import Config
            from pymongo import MongoClient
        except ImportError as exc:
            raise AssertionError(
                f"Fixture user {LOGIN_EMAIL!r} exists with a different password, "
                "and pymongo/config are unavailable to reset it."
            ) from exc

        cfg = Config()
        uri = cfg["database"]["uri"]
        db_name = cfg["database"]["name"]
        user_coll = cfg["database"]["user_collection"]
        if not uri or not db_name or not user_coll:
            raise AssertionError(
                f"Fixture user {LOGIN_EMAIL!r} exists with a different password, "
                "and MongoDB config is incomplete to reset it."
            )

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        try:
            result = client[db_name][user_coll].update_one(
                {"email": LOGIN_EMAIL},
                {"$set": {"password": LOGIN_PASSWORD, "name": LOGIN_NAME}},
            )
        finally:
            client.close()

        if result.matched_count != 1:
            raise AssertionError(
                f"Could not reset password for fixture user {LOGIN_EMAIL!r} "
                f"(matched={result.matched_count})"
            )

    # ------------------------------------------------------------------ #
    # 6. Login — valid credentials and edge cases
    # ------------------------------------------------------------------ #

    def test_6_login_valid_and_edge_cases(self) -> None:
        """Login succeeds for the fixture user and rejects auth edge cases."""
        status, body = _http_get_json(
            "/users/login",
            {"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        )
        self.assertEqual(status, 200, f"Valid login failed: {body}")
        self.assertIsInstance(body, dict)
        self.assertTrue(body.get("success"), f"Valid login unsuccessful: {body}")
        self.assertIn("data", body)
        self.assertEqual(body["data"].get("email"), LOGIN_EMAIL)
        self.assertEqual(body["data"].get("password"), LOGIN_PASSWORD)

        cases = (
            ("missing_both", None, 400, ("email", "password")),
            ("missing_email", {"password": LOGIN_PASSWORD}, 400, ("email",)),
            ("missing_password", {"email": LOGIN_EMAIL}, 400, ("password",)),
            (
                "wrong_password",
                {"email": LOGIN_EMAIL, "password": "not-the-right-password"},
                401,
                ("password",),
            ),
            (
                "unregistered_email",
                {
                    "email": "not-registered-acceptance@example.com",
                    "password": LOGIN_PASSWORD,
                },
                401,
                ("email",),
            ),
            (
                "empty_email",
                {"email": "", "password": LOGIN_PASSWORD},
                400,
                ("email",),
            ),
            (
                "empty_password",
                {"email": LOGIN_EMAIL, "password": ""},
                400,
                ("password",),
            ),
        )

        for label, params, expected_status, flagged in cases:
            with self.subTest(case=label):
                if params is None:
                    edge_status, edge_body = _http_get_json("/users/login")
                else:
                    edge_status, edge_body = _http_get_json("/users/login", params)

                self.assertEqual(
                    edge_status,
                    expected_status,
                    f"{label}: expected HTTP {expected_status}, got {edge_status}: {edge_body}",
                )
                self.assertIsInstance(edge_body, dict)
                self.assertFalse(
                    edge_body.get("success", False),
                    f"{label}: success should be false: {edge_body}",
                )
                for flag in flagged:
                    self.assertTrue(
                        edge_body.get(flag),
                        f"{label}: expected '{flag}' flag set: {edge_body}",
                    )

    # ------------------------------------------------------------------ #
    # 7. Null / empty OPL text rejected on save
    # ------------------------------------------------------------------ #

    def test_7_null_opl_text_rejected(self) -> None:
        """Saving null, empty, whitespace, or missing OPL text returns 400."""
        payloads = (
            ("null", {"opl": None, "user_id": USER_ID, "file_name": "null.opl"}),
            ("empty", {"opl": "", "user_id": USER_ID, "file_name": "empty.opl"}),
            ("whitespace", {"opl": "   \n\t  ", "user_id": USER_ID, "file_name": "ws.opl"}),
            ("missing", {"user_id": USER_ID, "file_name": "missing.opl"}),
        )

        for label, payload in payloads:
            with self.subTest(case=label):
                status, body = _http_post_json("/file/save", payload)
                self.assertEqual(
                    status,
                    400,
                    f"{label}: expected HTTP 400, got {status}: {body}",
                )
                self.assertIsInstance(body, dict)
                self.assertFalse(body.get("success", True), f"{label}: {body}")
                self.assertIn("OPL", str(body.get("message", "")), f"{label}: {body}")

    # ------------------------------------------------------------------ #
    # 8. Register rejects incomplete payloads
    # ------------------------------------------------------------------ #

    def test_8_register_rejects_incomplete_payload(self) -> None:
        """Registration requires name, email, and password."""
        cases = (
            ("empty_object", {}, ("name",)),
            ("missing_name", {"email": "a@b.com", "password": "x"}, ("name",)),
            ("missing_email", {"name": "A", "password": "x"}, ("email",)),
            ("missing_password", {"name": "A", "email": "a@b.com"}, ("password",)),
            (
                "empty_fields",
                {"name": "", "email": "", "password": ""},
                ("name",),
            ),
        )

        for label, payload, flagged in cases:
            with self.subTest(case=label):
                status, body = _http_post_json("/users/register", payload)
                self.assertEqual(
                    status,
                    400,
                    f"{label}: expected HTTP 400, got {status}: {body}",
                )
                self.assertIsInstance(body, dict)
                self.assertFalse(body.get("success", False), f"{label}: {body}")
                for flag in flagged:
                    self.assertTrue(
                        body.get(flag),
                        f"{label}: expected '{flag}' flag set: {body}",
                    )

    # ------------------------------------------------------------------ #
    # 9. Get user by email
    # ------------------------------------------------------------------ #

    def test_9_get_user_by_email(self) -> None:
        """Known emails resolve; unknown emails return 404."""
        status, body = _http_get_json(f"/users/{urllib.parse.quote(LOGIN_EMAIL)}")
        self.assertEqual(status, 200, f"Get fixture user failed: {body}")
        self.assertIsInstance(body, dict)
        self.assertTrue(body.get("success"), body)
        self.assertEqual(body.get("data", {}).get("email"), LOGIN_EMAIL)

        missing = "missing-user-acceptance@example.com"
        status, body = _http_get_json(f"/users/{urllib.parse.quote(missing)}")
        self.assertEqual(status, 404, f"Expected 404 for unknown user: {body}")
        self.assertIsInstance(body, dict)
        self.assertFalse(body.get("success", True), body)

    # ------------------------------------------------------------------ #
    # 10. Valid OPL save + unknown evaluation lookup
    # ------------------------------------------------------------------ #

    def test_10_save_valid_opl_and_unknown_evaluation(self) -> None:
        """A non-empty OPL saves successfully; unknown evaluation ids 404."""
        status, body = _http_post_json(
            "/file/save",
            {
                "opl": "Object Person.\nPerson is physical.",
                "user_id": USER_ID,
                "file_name": "unit_test_valid.opl",
            },
        )
        self.assertEqual(status, 200, f"Valid OPL save failed: {body}")
        self.assertIsInstance(body, dict)
        self.assertTrue(body.get("success"), body)
        opl_id = body.get("data")
        self.assertIsInstance(opl_id, str)
        self.assertTrue(opl_id, f"No opl_id returned: {body}")

        # Persisted content is readable for the owning user.
        get_status, get_body = _http_get_json(
            f"/file/opl/{opl_id}",
            {"user_id": USER_ID},
        )
        self.assertEqual(get_status, 200, f"OPL fetch failed: {get_body}")
        self.assertTrue(get_body.get("success"), get_body)
        self.assertIn("Person", str(get_body.get("data", "")))

        # Unknown ObjectId-shaped id has no evaluation.
        unknown_id = "000000000000000000000000"
        eval_status, eval_body = _http_get_json(f"/file/evaluation/{unknown_id}")
        self.assertEqual(
            eval_status,
            404,
            f"Expected 404 for unknown evaluation: {eval_body}",
        )
        self.assertIsInstance(eval_body, dict)
        self.assertFalse(eval_body.get("success", True), eval_body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
