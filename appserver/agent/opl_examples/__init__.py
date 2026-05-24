"""Demo OPL files for development until MongoDB loaders are implemented."""

from pathlib import Path

_DIR = Path(__file__).resolve().parent

demo1 = (_DIR / "demo1.opl").read_text(encoding="utf-8")
demo2 = (_DIR / "demo2.opl").read_text(encoding="utf-8")
