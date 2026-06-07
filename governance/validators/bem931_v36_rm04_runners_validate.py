#!/usr/bin/env python3
"""Validate BEM-931 v3.6 RM-04 runner files."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = [
    "gd_curator_runner.py", "dir_curator_runner.py", "wrk_curator_runner.py",
    "analyst_stage_runner.py", "auditor_stage_runner.py", "executor_stage_runner.py",
]

def has_main(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in ast.walk(tree))

def main() -> int:
    for name in RUNNERS:
        path = ROOT / "governance" / "runners" / name
        assert path.exists(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert len(text.encode("utf-8")) > 300, f"runner too small: {name}"
        tree = ast.parse(text, filename=str(path))
        assert has_main(tree), f"main() missing: {name}"
        assert "write_result" in text, f"result writer missing: {name}"
    print("PASS: BEM-931 v3.6 RM-04 runner files are executable Python, not stubs")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
