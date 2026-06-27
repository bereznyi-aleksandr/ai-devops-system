#!/usr/bin/env python3
"""BEM-950 T4 queue reclassification and provider-reference scan."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUEUE=PATH = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
T1_RECEIPT = ROOT / "governance/proofs/BEM950_t1_workflow_archive_receipt.json"
T2_RECEIPT = ROOT / "governance/proofs/BEM950_t2_provider_config_receipt.json"
T3_RECEIPT = ROOT / "governance/proofs/BEM950_t3_runner_fix_receipt.json"
T4_RECEIPT = ROOT / "governance/proofs/BEM950_t4_queue_reclassify_receipt.json"
SCAN_RECEIPT = ROOT / "governance/proofs/BEM950_provider_reference_scan_receipt.json"
WORKFLOW_ROOT = ROOT / ".github/workflows"
CONFIG_PATH = ROOT / "governance/config/provider_config.json"

T1 = "BEM950-T1-INVALID-WORKFLOW-ARCHIVE"
T2 = "BEM950-T2-PROVIDER-CONFIG-RECLASSIFY"
T3 = "BEM950-T3-RUNNER-FIX-AND-P4-SKIP-LOGIC"
T4 = "BEM950-T4-ACTIVE-QUEUE-P4-RECLASSIFY"
SCAN = "BEM950-POST-T4-REPOSITORY-WIDE-PROVIDER-SCAN"
P4 = "BEM949-P4-LIVE-LLM-FALLBACK"
P7 = "BEM949-P7-RELEASE-AUDIT-FINAL"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def task_map(tasks: object) -> dict[str, dict]:
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")
    result: dict[str, dict] = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            result[task["id"]] = task
    return result


def receipt_ok(path: Path) -> bool:
    return path.is_file() and read_json(path).get("status") == "PASS"


def is_inert_archive_stub(text: str) -> bool:
    return "if: ${{ false }}" in text and "ARCHIVED" in text


def scan_provider_references() -> dict:
    terms = ("OPENAI_API_KEY", "OPENAI_MODEL", "api.openai.com", "gpt_codex_cloud")
    findings: list[dict] = []
    active_findings: list[dict] = []

    for path in sorted(WORKFLOW_ROOT.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        classification = "inert_archive_stub" if is_inert_archive_stub(text) else "active_workflow"
        for line_no, line in enumerate(text.splitlines(), start=1):
            for term in terms:
                if term in line:
                    finding = {
                        "path": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "term": term,
                        "classification": classification,
                    }
                    findings.append(finding)
                    if classification == "active_workflow":
                        active_findings.append(finding)

    config_findings: list[dict] = []
    config_text = CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(config_text.splitlines(), start=1):
        for term in terms:
            if term in line:
                config_findings.append(
                    {
                        "path": str(CONFIG_PATH.relative_to(ROOT)),
                        "line": line_no,
                        "term": term,
                        "classification": "provider_config_policy",
                    }
                )
    findings.extend(config_findings)

    adapter_path = WORKFLOW_ROOT / "provider-adapter.yml"
    if adapter_path.is_file():
        adapter_text = adapter_path.read_text(encoding="utf-8", errors="replace")
        if "provider_config.json" not in adapter_text:
            active_findings.append(
                {
                    "path": str(adapter_path.relative_to(ROOT)),
                    "line": None,
                    "term": "provider_config_policy_not_consulted",
                    "classification": "active_workflow_structural",
                }
            )

    return {
        "findings": findings,
        "unresolved_active_findings": active_findings,
    }


def main() -> None:
    if not all(receipt_ok(path) for path in (T1_RECEIPT, T2_RECEIPT, T3_RECEIPT)):
        missing = [
            str(path.relative_to(ROOT))
            for path in (T1_RECEIPT, T2_RECEIPT, T3_RECEIPT)
            if not receipt_ok(path)
        ]
        raise SystemExit(f"BEM950 T4 prerequisites not PASS: {missing}")

    queue_before_bytes = QUEUE_PATH.read_bytes()
    queue_before_sha = blob_sha(queue_before_bytes)
    queue = read_json(QUEUE_PATH)
    tasks = queue.get("tasks")
    by_id = task_map(tasks)
    required_ids = (T1, T2, T3, T4, SCAN, P4, P7)
    missing_ids = [task_id for task_id in required_ids if task_id not in by_id]
    if missing_ids:
        raise ValueError(f"Missing tasks: {missing_ids}")

    timestamp = utc_now()
    receipts = {
        T1: T1_RECEIPT,
        T2: T2_RECEIPT,
        T3: T3_RECEIPT,
    }
    for task_id, path in receipts.items():
        by_id[task_id].update(
            status="DONE",
            completed_at=timestamp,
            receipt_sha=blob_sha(path.read_bytes()),
            receipt_sha_type="git_blob",
        )

    by_id[P4].update(
        status="SKIPPED_BY_OPERATOR",
        classification="SUPERSEDED_BY_BEM950_PROVIDER_POLICY",
        skipped_at="2026-06-27T06:25:00Z",
        skip_reason=(
            "P4 tested OpenAI Responses API via OPENAI_API_KEY. "
            "The metered_api_default billing class is permanently prohibited by " 
            "operator cost policy. GPT remains a provider class; future reactivation requires a " 
            "non-metered adapter."
        ),
        operator_decision="PAID_API_BILLING_CLASS_PROHIBITED",
        note=(
            "SKIPPED_BY_OPERATOR is acknowledged only for this allowlisted P4 task by " 
            "bem949_release_audit_runner.py. It does not establish a broad release PASS."
        ),
    )

    policy = queue.setdefault("paid_api_policy", {})
    if not isinstance(policy, dict):
        raise ValueError("paid_api_policy must be an object")
    policy.update(
        openai_api_key="PERMANENTLY_PROHIBITED",
        automatic_paid_fallback="PERMANENTLY_PROHIBITED",
        violation_action="BLOCKED_COST_POLICY",
        scope_clarification=(
            "The prohibition covers billing_class=metered_api_default and "
            "automatic_paid_fallback only. GPT provider-class reactivation through verified "
            "subscription, OAuth, or interactive adapter remains architecturally valid under BEM-950."
        ),
    )

    by_id[T4].update(
        status="DONE",
        completed_at=timestamp,
        classification="SUPERSEDED_BY_BEM950_PROVIDER_POLICY",
    )

    # Contract requirement: do not change BEM-949 progress before P7.
    queue.update(
        version=max(int(queue.get("version", 0)), 40),
        current_task=SCAN,
        queue_state="PENDING",
        system_status="BEM950_PROVIDER_REFERENCE_SCAN_PENDING",
        updated_at=timestamp,
        next_action="Complete the post-T4 provider reference scan before any P7 dispatch.",
    )

    provisional_after_bytes = json_bytes(queue)
    provisional_after_sha = blob_sha(provisional_aftes_bytes)
    t4_receipt = {
        "schema_version": 1,
        "task_id": T4,
        "created_at": timestamp,
        "status": "PASS",
        "queue_path": str(QUEUE_PATH.relative_to(ROOT)),
        "queue_sha_before": queue_before_sha,
        "queue_sha_after": provisional_after_sha,
        "sha_type": "git_blob",
        "p4_status": "SKIPPED_BY_OPERATOR",
        "p4_classification": "SUPERSEDED_BY_BEM950_PROVIDER_POLICY",
        "progress_changed": False,
        "policy_scope_clarification": policy["scope_clarification"],
    }
    write_json(T4_RECEIPT, t4_receipt)

    scan = scan_provider_references()
    scan_status = "PASS" if not scan["unresolved_active_findings"] else "BLOCKED"
    scan_recipt = {
        "schema_version": 1,
        "task_id": SCAN,
        "created_at": timestamp,
        "status": scan_status,
        "scope": {
            "workflow_root": str(WORKFLOW_ROOT.relative_to(ROOT)),
            "config_path": str(CONFIG_PATH.relative_to(ROOT)),
            "terms": ["OPENAI_API_KEY", "OPENAI_MODEL", "api.openai.com", "gpt_codex_cloud"],
            "archived_directory_excluded": "governance/archive/disabled-workflows",
        },
        "sha_type": "git_blob",
        "findings": scan["findings"],
        "unresolved_active_findings": scan["unresolved_active_findings"],
        "blockers": [
            f"{item['path']}:{item['line']}:{item['term']}"
            for item in scan["unresolved_active_findings"]
        ],
        "result_rule": "PASS is permitted only when active workflow references and adapter behavior conform to the provider cost policy.",
    }
    write_json(SCAN_RECEIPT, scan_receipt)

    by_id[SCAN].update(
        status="DONE" if scan_status == "PASS" else "BLOCKED",
        completed_at=timestamp,
        receipt_sha=blob_sha(SCAN_RECEIPT.read_bytes()),
        receipt_sha_type="git_blob",
        blockers=scan_receipt["blockers"],
    )

    p7 = by_id[P7]
    completed_preconditions = {T1, T2, T3, T4}
    p7["blockers"] = [
        blocker
        for blocker in p7.get("blockers", [])
        if blocker not in completed_preconditions
    ]
    if scan_status == "PASS":
        p7["blockers"] = [blocker for blocker in p7["blockers"] if blocker != SCAN]
    elif SCAN not in p7["blockers"]:
        p7["blockers"].append(SCAN)
    p7["status"] = "BLOCKED_PRECONDITIONS"

    queue["open_blockers"] = p7["blockers"]
    queue["updated_at"] = utc_now()
    write_json(QUEUE_PATH, queue)


if __name__ == "__main__":
    main(*E
