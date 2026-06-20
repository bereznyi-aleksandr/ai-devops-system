#!/usr/bin/env python3
"""BEM-948 executable enforcement for evidence (RULE-011) and continuity (RULE-012)."""

import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE_DEFAULT = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
RUNNER_REL = "governance/runners/bem948_rule_enforcement_runner.py"
GUARD_REL = "governance/runners/active_queue_guard.py"
RULES = [f"RULE-{n:03d}" for n in range(4, 13)]


def now():
    return datetime.now(timezoe.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_errors(value, where="$"):
    out = []
    if isinstance(value, dict):
        for key, item in value.items():
            if (key == "sha" or key.endswith("_sha")) and isinstance(item, str) and item:
                if f"{key}_type" not in value and "sha_type" not in value:
                    out.append(f"{where}.{key}:sha_type_missing")
            out.extend(sha_errors(item, f"{where}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.extend(sha_errors(item, f"{where}[{index}]"))
    return out


def evidence_errors(receipt):
    out = sha_errors(receipt)
    runtime = receipt.get("runtime_execution_claim") is True or receipt.get("evidence_kind") == "runtime_execution"
    if receipt.get("status") == "PASS" and runtime:
        execution = receipt.get("execution")
        terminal = receipt.get("terminal_report")
        executed = isinstance(execution, dict) and any(
            execution.get(key) for key in ("executed_at", "completed_at", "run_id")
        )
        if not executed and not isinstance(terminal, dict):
            out.append("runtime_pass_without_executed_or_terminal_evidence")
    return out


def local_queue_errors(queue):
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        return ["tasks_list_missing"]
    runnable = [t for t in tasks if isinstance(t, dict) and t.get("status") in ("IN_PROGRESS", "PENDING)]
    current = queue.get("current_task")
    ids = {str(t.get("id")) for t in tasks if isinstance(t, dict) and t.get("id")}
    out = []
    if runnable:
        if not current:
            out.append("current_task_missing_with_runnable_task")
        elif str(current) not in ids:
            out.append("current_task_not_in_tasks")
        elif not any(str(t.get("id")) == str(current) for t in runnable):
            out.append("current_task_not_runnable")
        if queue.get("queue_state") not in ("ACTIVE", "IN_PROGRESS"):
            out.append("queue_state_not_active_with_runnable_task")
    elif current:
        out.append("current_task_set_without_runnable_task")
    return out


def legacy_queue_errors(root, queue):
    path = root / GUARD_REL
    try:
        spec = importlib.util.spec_from_file_location("bem948_active_queue_guard", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("load_failed")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.validate(queue)
        if not isinstance(result, dict):
            return ["legacy_guard_invalid_result"], {"status": "BLOCKED"}
        if result.get("status") != "PASS":
            return ["legacy_guard_rejected_queue"], result
        return [], result
    except Exception as exc:
        return [f"legacy_guard_error:{type(exc).__name__}"], {"status": "BLOCKED", "error": type(exc).__name_}


def self_tests(root):
    bad_receipt = {"status": "PASS", "runtime_execution_claim": True, "artifact_sha": "abc"}
    evidence = evidence_errors(bad_receipt)
    bad_queue = {"queue_state": "ACTIVE", "current_task": "MISSING", "tasks": [{"id": "P2", "status": "PENDING"}]}
    local = local_queue_errors(bad_queue)
    legacy, _ = legacy_queue_errors(root, bad_queue)
    return {
        "rule_011_missing_sha_type_rejected": any(x.endswith("artifact_sha:sha_type_missing") for x in evidence),
        "rule_011_runtime_pass_without_execution_rejected": "runtime_pass_without_executed_or_terminal_evidence" in evidence,
        "rule_012_local_invalid_queue_rejected": "current_task_not_in_tasks" in local,
        "rule_012_legacy_invalid_queue_rejected": bool(legacy),
    }


def build_receipt(root, queue_path, queue):
    runner = root / RUNNER_REL
    local = local_queue_errors(queue)
    legacy, legacy_result = legacy_queue_errors(root, queue)
    tests = self_tests(root)
    blockers = [*local, *legacy, *[name for name, ok in tests.items() if not ok]]
    rows = {
        rule: {
            "enforcement_status": "NOT_VERIFIED",
            "enforcement_paths": [],
            "note": "No code-backed mapping is claimed by this runtime inventory.",
        }
        for rule in RULES
    }
    rows["RULE-011"] = {
        "enforcement_status": "ENFORCED",
        "enforcement_paths": [RUNNER_REL],
        "runtime_checks": {
            "missing_sha_type_rejected": tests["rule_011_missing_sha_type_rejected"],
            "runtime_pass_without_execution_rejected": tests["rule_011_runtime_pass_without_execution_rejected"],
        },
    }
    rows["RULE-012"] = {
        "enforcement_status": "ENFORCED",
        "enforcement_paths": [RUNNER_REL, GUARD_REL],
        "runtime_checks": {
            "local_invalid_queue_rejected": tests["rule_012_local_invalid_queue_rejected"],
            "legacy_invalid_queue_rejected": tests["rule_012_legacy_invalid_queue_rejected"],
            "current_queue_local_valid": not local,
            "current_queue_legacy_guard_valid": not legacy,
        },
        "legacy_guard_result": legacy_result,
    }
    receipt = {
        "schema_version": 1,
        "protocol": "BEM-948",
        "task_id": "BEM948-P2-RULE-ENFORCEMENT-VERIFICATION",
        "created_at": now(),
        "status": "PASS" if not blockers else "BLOCKED",
        "evidence_kind": "runtime_execution",
        "runtime_execution_claim": True,
        "execution": {
            "executed_at": now(),
            "runner_path": RUNNER_REL,
            "runner_sha": sha256(runner),
            "runner_sha_type": "sha256_content",
            "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
            "github_workflow": os.getenv("GITHUB_WORKFLOW", ""),
        },
        "queue_input": {
            "path": str(queue_path.relative_to(root)),
            "queue_sha": sha256(queue_path),
            "queue_sha_type": "sha256_content",
        },
        "rules": rows,
        "required_enforcers": ["RULE-011", "RULE-012"],
        "verification_scope": "RULE-004 through RULE-010 are NOT_VERIFIED; RULE-011 and RULE-012 are runtime enforcers.",
        "blockers": blockers,
        "next_task": "BEM948-P3-PROVIDER-FAILOVER-LIVE-TEST" if not blockers else "BEM948-P2-AUTOREPAIR",
    }
    generated = evidence_errors(receipt)
    if generated:
        receipt["status"] = "BLOCKED"
        receipt["blockers"] = sorted(set(blockers + generated))
        receipt["next_task"] = "BEM948-P2-AUTOREPAIR"
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--queue", default=str(QUEUE_DEFAULT))
    parser.add_argument("--check-queue", action="store_true")
    parser.add_argument("--check-receipt")
    parser.add_argument("--write-receipt")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    queue_path = Path(args.queue).resolve()

    if args.check_receipt:
        errors = evidence_errors(load_json(Path(args.check_receipt).resolve()))
        print(json.dumps({"status": "PASS" if not errors else "BLOCKED", "violations": errors}, indent=2))
        if errors:
            raise SystemExit(1)
        return

    queue = load_json(queue_path)
    if args.check_queue:
        local = local_queue_errors(queue)
        legacy, legacy_result = legacy_queue_errors(root, queue)
        errors = local + legacy
        print(json.dumps({"status": "PASS" if not errors else "BLOCKED", "violations": errors, "legacy_guard_result": legacy_result}, indent=2))
        if errors:
            raise SystemExit(1)
        return

    receipt = build_receipt(root, queue_path, queue)
    if args.write_receipt:
        write_json(Path(args.write_receipt).resolve(), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.strict and receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
