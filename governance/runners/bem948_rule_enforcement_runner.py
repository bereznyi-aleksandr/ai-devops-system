\
#!/usr/bin/env python3
"""BEM-948 runtime enforcement inventory for RULE-004 through RULE-012.

RULE-011 rejects insufficient evidence claims.
RULE-012 rejects non-continuous ACTIVE_QUEUE states.
Other rules are inventoried conservatively: absence of code is reported as
absence, never inferred from policy prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RULE_IDS = [f"RULE-{number:03d}" for number in range(4, 13)]
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = ROOT / "governance" / "roadmap" / "ACTIVE_QUEUE.json"
DEFAULT_RECEIPT = ROOT / "governance" / "proofs" / "BEM948_p2_rule_enforcement_runtime_receipt.json"
RUNNER_PATH = Path("governance/runners/bem948_rule_enforcement_runner.py")
CONTINUITY_GUARD_PATH = Path("governance/runners/active_queue_guard.py")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_content(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def find_sha_type_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_sha") and isinstance(item, str) and item:
                typed_key = f"{key}_type"
                if typed_key not in value and "sha_type" not in value:
                    errors.append(f"{path}.{key}:sha_type_missing")
            errors.extend(find_sha_type_errors(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(find_sha_type_errors(item, f"{path}[{index}]"))
    return errors


def evidence_violations(receipt: dict[str, Any]) -> list[str]:
    violations = find_sha_type_errors(receipt)
    status = str(receipt.get("status") or "")
    runtime_claim = receipt.get("runtime_execution_claim") is True
    evidence_kind = str(receipt.get("evidence_kind") or "")
    is_runtime = runtime_claim or evidence_kind == "runtime_execution"
    if status == "PASS" and is_runtime:
        execution = receipt.get("execution")
        terminal = receipt.get("terminal_report")
        executed = False
        if isinstance(execution, dict):
            executed = bool(
                execution.get("executed_at")
                or execution.get("completed_at")
                or execution.get("run_id")
            )
        if not executed and not isinstance(terminal, dict):
            violations.append("runtime_pass_without_executed_or_terminal_evidence")
    return violations


def continuity_violations(queue: dict[str, Any]) -> list[str]:
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        return ["tasks_list_missing"]
    runnable = [
        task for task in tasks
        if isinstance(task, dict) and task.get("status") in {"IN_PROGRESS", "PENDING"}
    ]
    current = queue.get("current_task")
    task_ids = {
        str(task.get("id"))
        for task in tasks
        if isinstance(task, dict) and task.get("id")
    }
    violations: list[str] = []
    if runnable:
        if not current:
            violations.append("current_task_missing_with_runnable_task")
        elif str(current) not in task_ids:
            violations.append("current_task_not_in_tasks")
        elif not any(str(task.get("id")) == str(current) for task in runnable):
            violations.append("current_task_not_runnable")
        if queue.get("queue_state") not in {"ACTIVE", "IN_PROGRESS"}:
            violations.append("queue_state_not_active_with_runnable_task")
    else:
        if current:
            violations.append("current_task_set_without_runnable_task")
        if queue.get("queue_state") not in {"IDLE", "CLOSED", "OPERATOR_ASSISTANCE_REQUIRED"}:
            violations.append("queue_state_invalid_without_runnable_task")
    return violations


def source_has_entrypoint(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "def main(" in text and "if __name__" in text


def scan_literal_rule_references(root: Path, rule_id: str) -> list[str]:
    matches: list[str] = []
    for base in (root / "governance", root / ".github"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".md", ".yml", ".yaml"}:
                continue
            try:
                if rule_id in path.read_text(encoding="utf-8", errors="replace"):
                    matches.append(str(path.relative_to(root)))
            except OSError:
                continue
    return sorted(matches)


def inventory(root: Path, queue: dict[str, Any]) -> dict[str, Any]:
    runner_path = root / RUNNER_PATH
    continuity_guard = root / CONTINUITY_GUARD_PATH
    runner_ready = runner_path.is_file() and source_has_entrypoint(runner_path)
    continuity_ready = continuity_guard.is_file() and source_has_entrypoint(continuity_guard)

    sample_invalid_evidence = {
        "status": "PASS",
        "runtime_execution_claim": True,
        "artifact_sha": "abc123",
    }
    sample_invalid_queue = {
        "queue_state": "ACTIVE",
        "current_task": "MISSING",
        "tasks": [{"id": "BEM948-P2", "status": "PENDING"}],
    }

    rows: dict[str, Any] = {}
    for rule_id in RULE_IDS:
        literal_paths = scan_literal_rule_references(root, rule_id)
        rows[rule_id] = {
            "literal_references": literal_paths,
            "enforcement_status": "ABSENT_OR_UNMAPPED",
            "enforcement_paths": [],
            "note": "No code-backed mapping is asserted from a literal policy reference alone.",
        }

    rows["RULE-011"] = {
        "literal_references": scan_literal_rule_references(root, "RULE-011"),
        "enforcement_status": "ENFORCED" if runner_ready else "ABSENT",
        "enforcement_paths": [str(RUNNER_PATH)] if runner_ready else [],
        "runtime_check": {
            "invalid_pass_rejected": any(item.endswith("artifact_sha:sha_type_missing") for item in evidence_violations(sample_invalid_evidence)),
            "runtime_pass_without_execution_rejected": "runtime_pass_without_executed_or_terminal_evidence" in evidence_violations(sample_invalid_evidence),
        },
        "note": "Evidence enforcement is executable through --check-receipt and exercised during this run.",
    }
    rows["RULE-012"] = {
        "literal_references": scan_literal_rule_references(root, "RULE-012"),
        "enforcement_status": "ENFORCED" if runner_ready and continuity_ready else "ABSENT",
        "enforcement_paths": [str(RUNNER_PATH), str(CONTINUITY_GUARD_PATH)] if runner_ready and continuity_ready else [],
        "runtime_check": {
            "invalid_queue_rejected": "current_task_not_in_tasks" in continuity_violations(sample_invalid_queue),
            "active_queue_current_state_valid": not continuity_violations(queue),
        },
        "note": "Continuity enforcement is executable through --check-queue and composed with active_queue_guard.py.",
    }
    return rows


def build_receipt(root: Path, queue_path: Path, queue: dict[str, Any]) -> dict[str, Any]:
    runner_file = root / RUNNER_PATH
    rules = inventory(root, queue)
    required_ok = (
        rules["RULE-011"]["enforcement_status"] == "ENFORCED"
        and rules["RULE-012"]["enforcement_status"] == "ENFORCED"
        and all(rules["RULE-011"]["runtime_check"].values())
        and all(rules["RULE-012"]["runtime_check"].values())
    )
    return {
        "schema_version": 1,
        "protocol": "BEM-948",
        "task_id": "BEM948-P2-RULE-ENFORCEMENT-VERIFICATION",
        "created_at": utc_now(),
        "status": "PASS" if required_ok else "BLOCKED",
        "evidence_kind": "runtime_execution",
        "runtime_execution_claim": True,
        "execution": {
            "executed_at": utc_now(),
            "runner_path": str(RUNNER_PATH),
            "runner_sha": sha256_content(runner_file),
            "runner_sha_type": "sha256_content",
            "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
            "github_workflow": os.getenv("GITHUB_WORKFLOW", ""),
        },
        "queue_input": {
            "path": str(queue_path.relative_to(root)),
            "sha256": sha256_content(queue_path),
            "sha256_type": "sha256_content",
        },
        "rules": rules,
        "required_enforcers": ["RULE-011", "RULE-012"],
        "verification_scope": (
            "RULE-004 through RULE-010 are inventoried without inferring enforcement "
            "from documentation; RULE-011 and RULE-012 are executable enforcers."
        ),
        "blockers": [] if required_ok else ["required_rule_enforcer_missing_or_failed"],
        "next_task": "BEM948-P3-PROVIDER-FAILOVER-LIVE-TEST" if required_ok else "BEM948-P2-AUTOREPAIR",
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="BEM-948 rule enforcement runner")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--check-queue", action="store_true")
    parser.add_argument("--check-receipt")
    parser.add_argument("--write-receipt")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    queue_path = Path(args.queue).resolve()
    if args.check_receipt:
        receipt = read_json(Path(args.check_receipt).resolve())
        violations = evidence_violations(receipt)
        print(json.dumps({"status": "PASS" if not violations else "BLOCKED", "violations": violations}, indent=2))
        if violations:
            raise SystemExit(1)
        return

    queue = read_json(queue_path)
    if args.check_queue:
        violations = continuity_violations(queue)
        print(json.dumps({"status": "PASS" if not violations else "BLOCKED", "violations": violations}, indent=2))
        if violations:
            raise SystemExit(1)
        return

    receipt = build_receipt(root, queue_path, queue)
    destination = Path(args.write_receipt).resolve() if args.write_receipt else None
    if destination:
        write_json(destination, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.strict and receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
