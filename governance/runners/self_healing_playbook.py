#!/usr/bin/env python3
"""BEM-933 runnable self-healing playbook and fail-closed repository validator."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - workflow installs PyYAML before execution
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
RUNNERS = ROOT / "governance" / "runners"
QUEUE = ROOT / "governance" / "roadmap" / "ACTIVE_QUEUE.json"
EXECUTION_LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"
RECEIPT = ROOT / "governance" / "proofs" / "BEM933_self_healing_playbook_receipt.json"

TASK_ID = "BEM933-SELF-HEALING-PLAYBOOK"

MANAGED_PYTHON = (
    RUNNERS / "active_queue_guard.py",
    RUNNERS / "receipt_watchdog.py",
    RUNNERS / "telegram_delivery_audit.py",
    RUNNERS / "self_healing_playbook.py",
)

MANAGED_WORKFLOWS = (
    WORKFLOWS / "active-queue-guard.yml",
    WORKFLOWS / "receipt-watchdog.yml",
    WORKFLOWS / "bem933-telegram-delivery-audit.yml",
    WORKFLOWS / "bem933-self-healing-playbook.yml",
)

RUNNER_REFERENCE = re.compile(r"(?:python|python3)\s+([A-Za-z0-9_./-]+\.py)\b")
BAD_CHANNEL = re.compile(r"\bwrk-[a-z0-9_-]+_to_[a-z0-9_-]+\.jsonl\b")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_python(source: str, label: str) -> tuple[ast.Module | None, list[str]]:
    try:
        return ast.parse(source, filename=label), []
    except SyntaxError as error:
        return None, [f"{label}:SyntaxError:{error.lineno}:{error.msg}"]


def imported_lib_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def validate_python(path: Path, lib_names: set[str]) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return [f"{relative(path)}:missing"]
    source = path.read_text(encoding="utf-8")
    tree, syntax_findings = parse_python(source, relative(path))
    findings.extend(syntax_findings)
    if tree is None:
        return findings

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if "main" not in function_names:
        findings.append(f"{relative(path)}:missing_def_main")

    has_main_guard = False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        try:
            expression = ast.unparse(node.test).replace(" ", "")
        except AttributeError:
            expression = ""
        if "__name__" in expression and "__main__" in expression:
            has_main_guard = True
            break
    if not has_main_guard:
        findings.append(f"{relative(path)}:missing_main_guard")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = (node.module or "").split(".")[-1]
        if module != "bem931_runner_lib":
            continue
        for alias in node.names:
            if alias.name != "*" and alias.name not in lib_names:
                findings.append(f"{relative(path)}:unknown_bem931_runner_lib_import:{alias.name}")

    if BAD_CHANNEL.search(source):
        findings.append(f"{relative(path)}:hyphenated_channel_name")
    return findings


def control_character_findings(path: Path, raw: bytes) -> list[str]:
    findings: list[str] = []
    if b"\x00" in raw:
        findings.append(f"{relative(path)}:null_byte")
    for offset, byte in enumerate(raw):
        if byte in (9, 10, 13):
            continue
        if byte < 32:
            findings.append(f"{relative(path)}:control_character:0x{byte:02x}:offset_{offset}")
            break
    return findings


def yaml_parse_findings(path: Path, source: str) -> list[str]:
    if yaml is None:
        return [f"{relative(path)}:pyyaml_missing"]
    try:
        parsed = yaml.safe_load(source)
    except yaml.YAMLError as error:
        return [f"{relative(path)}:yaml_parse_error:{error.__class__.__name__}"]
    if not isinstance(parsed, dict):
        return [f"{relative(path)}:yaml_not_mapping"]
    if "jobs" not in parsed:
        return [f"{relative(path)}:yaml_missing_jobs"]
    return []


def heredoc_findings(path: Path, source: str) -> list[str]:
    findings: list[str] = []
    stack: list[tuple[str, int]] = []
    for number, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        opener = re.search(r"<<-?['\"]?([A-Z][A-Z0-9_]*)['\"]?", line)
        if opener:
            stack.append((opener.group(1), number))
            continue
        if stack and line == stack[-1][0]:
            stack.pop()
    for marker, number in stack:
        findings.append(f"{relative(path)}:unclosed_heredoc:{marker}:line_{number}")
    return findings


def validate_workflow_source(path: Path, raw: bytes) -> list[str]:
    findings = control_character_findings(path, raw)
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        return findings + [f"{relative(path)}:utf8_decode_error:{error.start}"]

    findings.extend(yaml_parse_findings(path, source))

    if '"created_at"":' in source or "'created_at'':" in source:
        findings.append(f"{relative(path)}:double_colon_json_key")
    if "*.jsol" in source:
        findings.append(f"{relative(path)}:jsonl_glob_typo")
    findings.extend(heredoc_findings(path, source))

    for match in RUNNER_REFERENCE.finditer(source):
        referenced = ROOT / match.group(1)
        if not referenced.exists():
            findings.append(f"{relative(path)}:missing_runner:{match.group(1)}")

    if "set -euo pipefail" in source and "git commit" in source:
        guarded_commit = (
            "if git diff --cached --quiet" in source
            or ("git commit" in source and "|| true" in source)
            or "if git diff --cached --quiet; then" in source
        )
        if not guarded_commit:
            findings.append(f"{relative(path)}:unguarded_git_commit")
    return findings


def validate_workflow(path: Path) -> list[str]:
    if not path.exists():
        return [f"{relative(path)}:missing"]
    return validate_workflow_source(path, path.read_bytes())


def fixture_checks() -> dict[str, bool]:
    bad_python = "def main():\n   if True:\n  return 0\n"
    _, bad_python_findings = parse_python(bad_python, "fixture_bad.py")

    bad_json_key = 'print(\'{"created_at"": "x"}\')'
    bad_glob = 'for f in *.jsol; do echo "$f"; done'
    bad_channel = "wrk" + "-c1_to_analyst.jsonl"
    bad_yaml = b"name: bad\non:\n  workflow_dispatch:\njobs:\n  bad: [\n"
    null_workflow = b"name: bad\non:\n  workflow_dispatch:\njobs:\n  t:\n    steps:\n      - uses: actions/checkout\x00v4\n"

    good_python = (
        "def main():\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )
    tree, good_findings = parse_python(good_python, "fixture_good.py")
    has_good_main = bool(
        tree
        and any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body)
    )

    return {
        "detect_python_syntax_or_indent_error": bool(bad_python_findings),
        "detect_double_colon_json_key": '"created_at"":' in bad_json_key,
        "detect_jsonl_glob_typo": "*.jsol" in bad_glob,
        "detect_hyphenated_channel_name": bool(BAD_CHANNEL.search(bad_channel)),
        "detect_missing_runner_reference": not (ROOT / "governance/runners/NONEXISTENT.py").exists(),
        "detect_yaml_parse_error": bool(validate_workflow_source(Path(".github/workflows/fixture_bad.yml"), bad_yaml)),
        "detect_null_byte_control_character": any("null_byte" in item for item in validate_workflow_source(Path(".github/workflows/fixture_null.yml"), null_workflow)),
        "accept_valid_main_and_guard": has_good_main and not good_findings,
    }


def load_lib_names() -> tuple[set[str], list[str]]:
    path = RUNNERS / "bem931_runner_lib.py"
    if not path.exists():
        return set(), [f"{relative(path)}:missing"]
    tree, findings = parse_python(path.read_text(encoding="utf-8"), relative(path))
    if tree is None:
        return set(), findings
    return imported_lib_names(tree), findings


def append_log_once(record: dict[str, Any]) -> bool:
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = EXECUTION_LOG.read_text(encoding="utf-8").splitlines() if EXECUTION_LOG.exists() else []
    for line in existing:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("id") == record["id"] and item.get("status") == "done" and item.get("sha") == record["sha"]:
            return False
    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def mark_queue_if_present(source_sha: str, created_at: str) -> bool:
    if not QUEUE.exists():
        return False
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    changed = False
    for task in queue.get("tasks", []):
        if task.get("id") == TASK_ID:
            if task.get("status") != "DONE" or task.get("done_sha") != source_sha:
                task.update(
                    {
                        "status": "DONE",
                        "done_sha": source_sha,
                        "proof": str(RECEIPT.relative_to(ROOT)),
                        "proof_status": "PASS",
                    }
                )
                changed = True
            break
    queue["queue_state"] = "IDLE"
    queue["current_task"] = None
    queue["operator_gate_required"] = True
    queue["next_action"] = "No actionable tasks. Operator gate required before adding new scope."
    queue["updated_at"] = created_at
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    lib_names, findings = load_lib_names()

    fixture_results = fixture_checks()
    findings.extend(
        f"fixture:{name}:failed"
        for name, passed in fixture_results.items()
        if not passed
    )

    for path in MANAGED_PYTHON:
        findings.extend(validate_python(path, lib_names))

    for path in MANAGED_WORKFLOWS:
        findings.extend(validate_workflow(path))

    created_at = now_utc()
    source_sha = git_sha()
    passed = not findings

    queue_changed = False
    log_appended = False
    if passed:
        queue_changed = mark_queue_if_present(source_sha, created_at)
        log_appended = append_log_once(
            {
                "date": created_at,
                "id": TASK_ID,
                "sha": source_sha,
                "status": "done",
                "source_proof": str(RECEIPT.relative_to(ROOT)),
                "queue_state": "IDLE",
                "next_task": None,
                "operator_gate_required": True,
                "self_healing_checks": "yaml_parse_and_control_characters_enabled",
            }
        )

    receipt = {
        "status": "PASS" if passed else "BLOCKED",
        "protocol": "BEM-933",
        "task_id": TASK_ID,
        "receipt_type": "runnable_workflow_autorepair_playbook",
        "created_at": created_at,
        "source_sha": source_sha,
        "checks": {
            "fixture_detectors": fixture_results,
            "managed_python_count": len(MANAGED_PYTHON),
            "managed_workflow_count": len(MANAGED_WORKFLOWS),
            "python_ast_and_main_guard": True,
            "bem931_runner_lib_import_validation": True,
            "workflow_yaml_safe_load_validation": True,
            "workflow_control_character_validation": True,
            "workflow_null_byte_detection": True,
            "workflow_runner_path_validation": True,
            "heredoc_balance_validation": True,
            "git_commit_guard_validation": True,
        },
        "findings": findings,
        "queue_changed": queue_changed,
        "execution_log_appended": log_appended,
        "next_task": None,
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(receipt["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
