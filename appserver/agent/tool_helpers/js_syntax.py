"""JavaScript/JSX syntax checks for generated project zips."""

from __future__ import annotations

import re

try:
    import esprima
except ImportError:
    esprima = None


def _check_js_structure_fallback(source: str) -> bool:
    """Lightweight bracket/string balancer when esprima2 is unavailable."""
    if not source.strip():
        return False

    stack: list[str] = []
    in_string: str | None = None
    escape = False
    pairs = {"(": ")", "[": "]", "{": "}"}

    for ch in source:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if in_string:
            if ch == in_string:
                in_string = None
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            continue
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False

    return not stack and in_string is None


def _prepare_jsx_for_esprima(source: str) -> str:
    """Best-effort prep for JSX patterns esprima2 may not parse."""
    source = re.sub(r"<\s*>", "<React.Fragment>", source)
    source = re.sub(r"<\s*/\s*>", "</React.Fragment>", source)
    return source


def check_js_syntax(source: str, *, path: str = "") -> bool:
    """
    Parse JS/JSX source with esprima2, falling back to bracket balancing.

    params:
        - source: File contents
        - path: Zip-relative path (used for module vs script and JSX detection)

    returns:
        - bool: True if syntax is valid
    """
    if not source.strip():
        return False

    if esprima is None:
        return _check_js_structure_fallback(source)

    is_jsx = path.endswith(".jsx")
    is_module = (
        path.endswith((".jsx", ".mjs"))
        or "import " in source
        or "export " in source
    )
    prepared = _prepare_jsx_for_esprima(source)
    options = {"jsx": is_jsx}

    try:
        if is_module:
            esprima.parseModule(prepared, options)
        else:
            esprima.parseScript(prepared, options)
        return True
    except Exception:
        return False
