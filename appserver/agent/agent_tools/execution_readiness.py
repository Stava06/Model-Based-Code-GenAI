"""
Static execution-readiness checks for generated fullstack zips.

Answers: "Will this project execute when the user runs it locally?"
Uses only in-memory analysis — no subprocess, npm, pip, or Node on the server.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any

REQUIRED_FRONTEND_PATHS = (
    "frontend/package.json",
    "frontend/index.html",
    "frontend/vite.config.js",
    "frontend/src/main.jsx",
    "frontend/src/App.jsx",
    "frontend/src/service.js",
)
REQUIRED_BACKEND_PATHS = (
    "backend/app.py",
    "backend/requirements.txt",
)

_FLASK_ROUTE_RE = re.compile(
    r"@app\.(?:route|get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_AXIOS_CALL_RE = re.compile(
    r"axios\.(?:get|post|put|delete|patch)\(\s*"
    r"(?:`([^`]+)`|'([^']+)'|\"([^\"]+)\")",
    re.MULTILINE | re.IGNORECASE,
)
_API_PATH_FRAGMENT_RE = re.compile(r"(/api/[A-Za-z0-9_./:${}-]+)")
_RELATIVE_IMPORT_RE = re.compile(
    r"""from\s+['"](\./[^'"]+)['"]|import\s+['"](\./[^'"]+)['"]"""
)
_API_URL_IN_PATH_RE = re.compile(
    r"\$\{API_URL\}([^`'\"]+)|\$\{import\.meta\.env\.VITE_API_URL\}([^`'\"]+)",
)


@dataclass(frozen=True)
class ExecutionCheck:
    name: str
    passed: bool
    detail: str = ""


def _non_empty(files: dict[str, str], path: str) -> bool:
    return bool(files.get(path, "").strip())


def _normalize_api_path(path: str) -> str | None:
    path = path.strip()
    if not path or "API_URL" in path and not _API_URL_IN_PATH_RE.search(path):
        return None
    api_url_match = _API_URL_IN_PATH_RE.search(path)
    if api_url_match:
        path = (api_url_match.group(1) or api_url_match.group(2) or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        match = re.search(r"https?://[^/]+(/.*)$", path)
        path = match.group(1) if match else None
    if not path:
        return None
    if not path.startswith("/"):
        path = "/" + path
    path = path.split("?")[0]
    path = re.sub(r"\$\{[^}]+\}", ":param", path)
    path = re.sub(r"<[^>]+>", ":param", path)
    return path.rstrip("/") or "/"


def _extract_flask_routes(app_py: str) -> set[str]:
    routes: set[str] = set()
    for match in _FLASK_ROUTE_RE.finditer(app_py):
        normalized = _normalize_api_path(match.group(1))
        if normalized:
            routes.add(normalized)
    return routes


def _extract_service_routes(service_js: str) -> set[str]:
    routes: set[str] = set()
    for match in _AXIOS_CALL_RE.finditer(service_js):
        raw = match.group(1) or match.group(2) or match.group(3) or ""
        normalized = _normalize_api_path(raw)
        if normalized:
            routes.add(normalized)
    for match in _API_PATH_FRAGMENT_RE.finditer(service_js):
        normalized = _normalize_api_path(match.group(1))
        if normalized:
            routes.add(normalized)
    return routes


def _service_calls_backend_api(service_js: str) -> bool:
    if _extract_service_routes(service_js):
        return True
    return bool(re.search(r"\baxios\.[a-z]+\s*\(", service_js, re.IGNORECASE)) and (
        "/api/" in service_js or "API_URL" in service_js
    )


def _resolve_relative_import(base_dir: str, import_path: str) -> list[str]:
    import_path = import_path.removeprefix("./")
    base_parts = base_dir.split("/") if base_dir else []
    target_parts: list[str] = []
    for part in (*base_parts, *import_path.split("/")):
        if part in ("", "."):
            continue
        if part == "..":
            if target_parts:
                target_parts.pop()
            continue
        target_parts.append(part)
    stem = "/".join(target_parts)
    return [
        f"frontend/{stem}",
        f"frontend/{stem}.js",
        f"frontend/{stem}.jsx",
        f"frontend/{stem}/index.js",
        f"frontend/{stem}/index.jsx",
    ]


def _check_flask_app_structure(app_py: str) -> list[ExecutionCheck]:
    checks: list[ExecutionCheck] = []
    try:
        tree = ast.parse(app_py)
        compile(app_py, "backend/app.py", "exec")
    except (SyntaxError, ValueError) as exc:
        return [ExecutionCheck("backend/app.py compiles", False, str(exc))]

    has_flask = False
    has_cors_import = False
    has_app_assign = False
    has_cors_call = False
    has_route = False
    has_main_guard = False
    has_app_run = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "flask" and any(alias.name == "Flask" for alias in node.names):
                has_flask = True
            if node.module == "flask_cors" and any(alias.name == "CORS" for alias in node.names):
                has_cors_import = True
        elif isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "app"
                for target in node.targets
            ) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name) and func.id == "Flask":
                    has_app_assign = True
                elif isinstance(func, ast.Attribute) and func.attr == "Flask":
                    has_app_assign = True
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "CORS"
                and call.args
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "app"
            ):
                has_cors_call = True
        elif isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if _is_flask_route_decorator(decorator):
                    has_route = True
                    break
        elif isinstance(node, ast.If) and _is_main_guard(node.test):
            has_main_guard = True
            for child in node.body:
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                    if _is_app_run_call(child.value):
                        has_app_run = True
                elif isinstance(child, ast.Call) and _is_app_run_call(child):
                    has_app_run = True

    checks.extend(
        [
            ExecutionCheck("backend imports Flask", has_flask),
            ExecutionCheck("backend imports CORS from flask_cors", has_cors_import),
            ExecutionCheck("backend defines app = Flask(__name__)", has_app_assign),
            ExecutionCheck("backend calls CORS(app)", has_cors_call),
            ExecutionCheck("backend defines at least one @app route", has_route),
            ExecutionCheck('backend has if __name__ == "__main__" guard', has_main_guard),
            ExecutionCheck("backend calls app.run() in main guard", has_app_run),
        ]
    )
    return checks


def _is_main_guard(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if isinstance(left, ast.Name) and left.id == "__name__":
        return isinstance(right, ast.Constant) and right.value == "__main__"
    if isinstance(right, ast.Name) and right.id == "__name__":
        return isinstance(left, ast.Constant) and left.value == "__main__"
    return False


def _is_app_run_call(call: ast.Call) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and func.attr == "run" and (
        (isinstance(func.value, ast.Name) and func.value.id == "app")
    )


def _is_flask_route_decorator(decorator: ast.AST) -> bool:
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Attribute) and func.attr in {
            "route",
            "get",
            "post",
            "put",
            "delete",
            "patch",
        }:
            return isinstance(func.value, ast.Name) and func.value.id == "app"
    return False


def _check_package_json(package_json: str) -> list[ExecutionCheck]:
    checks: list[ExecutionCheck] = []
    try:
        pkg = json.loads(package_json)
    except json.JSONDecodeError as exc:
        return [ExecutionCheck("frontend/package.json is valid JSON", False, str(exc))]

    if not isinstance(pkg, dict):
        return [ExecutionCheck("frontend/package.json is an object", False)]

    scripts = pkg.get("scripts") or {}
    deps = {str(k).lower() for k in (pkg.get("dependencies") or {})}
    dev_deps = {str(k).lower() for k in (pkg.get("devDependencies") or {})}

    checks.extend(
        [
            ExecutionCheck("frontend/package.json has name", bool(str(pkg.get("name", "")).strip())),
            ExecutionCheck("frontend/package.json type is module", pkg.get("type") == "module"),
            ExecutionCheck(
                "frontend/package.json has dev script for vite",
                isinstance(scripts.get("dev"), str) and "vite" in scripts["dev"],
            ),
            ExecutionCheck("frontend/package.json depends on react", "react" in deps),
            ExecutionCheck("frontend/package.json depends on react-dom", "react-dom" in deps),
            ExecutionCheck("frontend/package.json depends on axios", "axios" in deps),
            ExecutionCheck("frontend/package.json devDepends on vite", "vite" in dev_deps),
            ExecutionCheck(
                "frontend/package.json devDepends on @vitejs/plugin-react",
                "@vitejs/plugin-react" in dev_deps,
            ),
        ]
    )
    return checks


def _check_requirements(requirements: str) -> list[ExecutionCheck]:
    lines = [
        line.strip().lower().split("#")[0].strip()
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    joined = "\n".join(lines)
    return [
        ExecutionCheck("backend/requirements.txt is non-empty", bool(lines)),
        ExecutionCheck("backend/requirements.txt includes flask", "flask" in joined),
        ExecutionCheck(
            "backend/requirements.txt includes flask-cors",
            "flask-cors" in joined or "flask_cors" in joined,
        ),
    ]


def _check_main_entry(main_jsx: str) -> list[ExecutionCheck]:
    imports_react = (
        "from 'react'" in main_jsx
        or 'from "react"' in main_jsx
        or "react-dom/client" in main_jsx
        or "react-dom" in main_jsx
    )
    return [
        ExecutionCheck("frontend/src/main.jsx imports React runtime", imports_react),
        ExecutionCheck(
            "frontend/src/main.jsx mounts to #root",
            "getElementById('root')" in main_jsx or 'getElementById("root")' in main_jsx,
        ),
        ExecutionCheck(
            "frontend/src/main.jsx imports App",
            "./App" in main_jsx or "./App.jsx" in main_jsx,
        ),
        ExecutionCheck(
            "frontend/src/main.jsx uses createRoot or render",
            "createRoot" in main_jsx or ".render(" in main_jsx,
        ),
    ]


def _check_app_component(app_jsx: str) -> list[ExecutionCheck]:
    return [
        ExecutionCheck("frontend/src/App.jsx has default export", "export default" in app_jsx),
        ExecutionCheck(
            "frontend/src/App.jsx renders JSX",
            "return" in app_jsx and ("<" in app_jsx and ">" in app_jsx),
        ),
    ]


def _check_frontend_service_usage(files: dict[str, str]) -> list[ExecutionCheck]:
    service_importers: list[str] = []
    direct_http_files: list[str] = []

    for path, source in files.items():
        if not path.startswith("frontend/src/") or not path.endswith((".js", ".jsx")):
            continue
        if path == "frontend/src/service.js":
            continue
        if "./service" in source or "./service.js" in source:
            service_importers.append(path)
        if re.search(r"\baxios\.|fetch\s*\(", source):
            direct_http_files.append(path)

    return [
        ExecutionCheck(
            "frontend UI imports service.js",
            bool(service_importers),
            "expected import from ./service.js in a UI file",
        ),
        ExecutionCheck(
            "frontend UI avoids direct axios/fetch",
            not direct_http_files,
            f"direct HTTP in: {', '.join(direct_http_files)}" if direct_http_files else "",
        ),
    ]


def _check_service_layer(service_js: str) -> list[ExecutionCheck]:
    has_export = "export " in service_js
    has_axios = "axios" in service_js
    has_api_url = (
        "import.meta.env.VITE_API_URL" in service_js
        or "localhost:5000" in service_js
        or "API_URL" in service_js
    )
    has_calls = _service_calls_backend_api(service_js)
    return [
        ExecutionCheck("frontend/src/service.js exports functions", has_export),
        ExecutionCheck("frontend/src/service.js uses axios", has_axios),
        ExecutionCheck("frontend/src/service.js defines API_URL", has_api_url),
        ExecutionCheck("frontend/src/service.js calls backend APIs", has_calls),
    ]


def _check_frontend_imports(files: dict[str, str]) -> list[ExecutionCheck]:
    checks: list[ExecutionCheck] = []
    for path, source in files.items():
        if not path.startswith("frontend/src/") or not path.endswith((".js", ".jsx")):
            continue
        base_dir = "/".join(path.removeprefix("frontend/").split("/")[:-1])
        for match in _RELATIVE_IMPORT_RE.finditer(source):
            import_path = match.group(1) or match.group(2) or ""
            candidates = _resolve_relative_import(base_dir, import_path)
            if not any(candidate in files and files[candidate].strip() for candidate in candidates):
                checks.append(
                    ExecutionCheck(
                        f"{path} import resolves ({import_path})",
                        False,
                        f"expected one of: {', '.join(candidates)}",
                    )
                )
            else:
                checks.append(
                    ExecutionCheck(f"{path} import resolves ({import_path})", True)
                )
    if not checks:
        checks.append(ExecutionCheck("frontend relative imports resolve", True))
    return checks


def _check_api_alignment(app_py: str, service_js: str) -> list[ExecutionCheck]:
    flask_routes = _extract_flask_routes(app_py)
    service_routes = _extract_service_routes(service_js)
    backend_has_api = bool(flask_routes)
    frontend_calls_api = _service_calls_backend_api(service_js)
    wired_together = backend_has_api and frontend_calls_api

    return [
        ExecutionCheck("backend exposes API routes", backend_has_api),
        ExecutionCheck("frontend service.js calls backend APIs", frontend_calls_api),
        ExecutionCheck(
            "frontend and backend are API-wired",
            wired_together,
            (
                f"backend routes: {', '.join(sorted(flask_routes))}; "
                f"frontend paths: {', '.join(sorted(service_routes))}"
            )
            if wired_together
            else "frontend should call APIs via service.js and backend should expose routes",
        ),
    ]


def run_execution_readiness_checks(files: dict[str, str]) -> list[ExecutionCheck]:
    """Run all static execution-readiness checks against zip file contents."""
    checks: list[ExecutionCheck] = []

    for path in (*REQUIRED_FRONTEND_PATHS, *REQUIRED_BACKEND_PATHS):
        present = _non_empty(files, path)
        checks.append(
            ExecutionCheck(f"required file present ({path})", present)
        )

    package_json = files.get("frontend/package.json", "")
    if package_json.strip():
        checks.extend(_check_package_json(package_json))

    index_html = files.get("frontend/index.html", "")
    if index_html:
        checks.extend(
            [
                ExecutionCheck(
                    "frontend/index.html mounts #root",
                    'id="root"' in index_html or "id='root'" in index_html,
                ),
                ExecutionCheck(
                    "frontend/index.html loads /src/main.jsx",
                    "/src/main.jsx" in index_html,
                ),
            ]
        )

    vite_config = files.get("frontend/vite.config.js", "")
    if vite_config:
        checks.extend(
            [
                ExecutionCheck("frontend/vite.config.js uses defineConfig", "defineConfig" in vite_config),
                ExecutionCheck(
                    "frontend/vite.config.js enables React plugin",
                    "plugin-react" in vite_config or "@vitejs/plugin-react" in vite_config,
                ),
            ]
        )

    main_jsx = files.get("frontend/src/main.jsx", "")
    if main_jsx.strip():
        checks.extend(_check_main_entry(main_jsx))

    app_jsx = files.get("frontend/src/App.jsx", "")
    if app_jsx.strip():
        checks.extend(_check_app_component(app_jsx))

    checks.extend(_check_frontend_service_usage(files))

    service_js = files.get("frontend/src/service.js", "")
    if service_js.strip():
        checks.extend(_check_service_layer(service_js))

    requirements = files.get("backend/requirements.txt", "")
    if requirements.strip():
        checks.extend(_check_requirements(requirements))

    app_py = files.get("backend/app.py", "")
    if app_py.strip():
        checks.extend(_check_flask_app_structure(app_py))

    if app_py.strip() and service_js.strip():
        checks.extend(_check_api_alignment(app_py, service_js))

    checks.extend(_check_frontend_imports(files))
    return checks


def execution_readiness_score(checks: list[ExecutionCheck]) -> dict[str, Any]:
    if not checks:
        return {
            "executable_score": 0.0,
            "passed_checks": 0,
            "failed_checks": 0,
            "failures": [],
        }

    passed = [check for check in checks if check.passed]
    failed = [check for check in checks if not check.passed]
    score = round((len(passed) / len(checks)) * 100, 2)
    return {
        "executable_score": score,
        "passed_checks": len(passed),
        "failed_checks": len(failed),
        "failures": [
            {"check": check.name, "detail": check.detail}
            for check in failed
        ],
    }
