#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "governance" / "exchange_ledger.csv"
EXECUTOR_RESULT = ROOT / "governance" / "runtime" / "results" / "executor_materialize_result.json"
AUDITOR_RESULT = ROOT / "governance" / "runtime" / "results" / "auditor_materialize_result.json"


class IntakeError(RuntimeError):
    pass


def detect_ledger_schema(header: List[str]) -> str:
    if len(header) == 14 and header[0] == "schema_version" and header[1] == "event_id":
        return "14-col"
    if len(header) >= 27 and header[0] == "protocol_version" and header[1] == "event_id":
        return "27-col"
    raise IntakeError("Unsupported ledger schema")


def read_last_row() -> Tuple[str, Dict[str, str]]:
    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise IntakeError("Ledger has no data rows")
    header = rows[0]
    schema = detect_ledger_schema(header)
    last = rows[-1]
    if len(last) != len(header):
        raise IntakeError("Last ledger row length mismatch")
    return schema, dict(zip(header, last))


def normalize_row(schema: str, row: Dict[str, str]) -> Dict[str, str]:
    if schema == "14-col":
        return {
            "protocol_version": row.get("schema_version", ""),
            "event_id": row.get("event_id", ""),
            "parent_event_id": row.get("parent_event_id", ""),
            "task_id": row.get("task_id", ""),
            "ts_utc": row.get("event_time", ""),
            "event_type": row.get("event_type", ""),
            "actor_role": row.get("actor_role", ""),
            "summary": row.get("description", ""),
            "state": row.get("status", ""),
            "next_role": row.get("next_actor_role", ""),
            "next_action": row.get("next_expected_event", ""),
            "artifact_ref": row.get("routing_decision_basis", ""),
            "commit_sha": row.get("commit_sha", ""),
        }
    if schema == "27-col":
        return {
            "protocol_version": row.get("protocol_version", ""),
            "event_id": row.get("event_id", ""),
            "parent_event_id": row.get("parent_event_id", ""),
            "task_id": row.get("task_id", ""),
            "ts_utc": row.get("ts_utc", ""),
            "event_type": row.get("event_type", ""),
            "actor_role": row.get("actor_role", ""),
            "summary": row.get("summary", ""),
            "state": row.get("state", ""),
            "next_role": row.get("next_role", ""),
            "next_action": row.get("next_action", ""),
            "artifact_ref": row.get("artifact_ref", ""),
            "commit_sha": row.get("commit_sha", ""),
        }
    raise IntakeError(f"Normalization for schema {schema} not implemented")


def choose_latest_result() -> Tuple[str, Path, dict]:
    candidates = []
    for role, path in (("EXECUTOR", EXECUTOR_RESULT), ("AUDITOR", AUDITOR_RESULT)):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            candidates.append((role, path, data))
    if not candidates:
        raise IntakeError("No result manifests found")
    candidates.sort(key=lambda x: x[2].get("ts_utc", ""))
    return candidates[-1]


def build_append_plan(role: str, result_data: dict, ledger: dict) -> dict:
    result = result_data.get("result", "")
    task_id = result_data.get("task_id", ledger.get("task_id", ""))
    input_event_id = result_data.get("input_event_id", ledger.get("event_id", ""))
    produced_artifact_path = result_data.get("produced_artifact_path", "")
    summary = result_data.get("summary", "")
    ts_utc = result_data.get("ts_utc", "")

    if role == "AUDITOR" and result == "SUCCESS":
        next_role = "EXECUTOR"
        next_action = "WRITE_PLAN"
        event_type = "TASK_APPROVED"
        state = "PLAN_PENDING"
    elif role == "EXECUTOR" and result == "SUCCESS":
        next_role = "AUDITOR"
        next_action = "REVIEW_TASK"
        event_type = "TASK_PROPOSED"
        state = "AUDIT_PENDING"
    elif result == "BLOCKED":
        next_role = ledger.get("next_role", "")
        next_action = ledger.get("next_action", "")
        event_type = f"{role}_BLOCKED"
        state = ledger.get("state", "")
    else:
        next_role = ""
        next_action = ""
        event_type = f"{role}_{result or 'UNKNOWN'}"
        state = ledger.get("state", "")

    event_id = f"{event_type}-{task_id}-AUTO-0001"

    row_14 = [
        ledger.get("protocol_version", ""),
        event_id,
        input_event_id,
        task_id,
        ts_utc,
        event_type,
        role,
        event_type,
        summary,
        state,
        next_role,
        next_action,
        produced_artifact_path,
        "LOCAL",
    ]

    return {
        "result_role": role,
        "result_value": result,
        "source_result_manifest": str((AUDITOR_RESULT if role == 'AUDITOR' else EXECUTOR_RESULT).relative_to(ROOT)),
        "ledger_append_plan": {
            "schema": "14-col",
            "header_order": [
                "schema_version",
                "event_id",
                "parent_event_id",
                "task_id",
                "event_time",
                "step_name",
                "actor_role",
                "event_type",
                "description",
                "status",
                "next_actor_role",
                "next_expected_event",
                "routing_decision_basis",
                "commit_sha"
            ],
            "proposed_row": row_14,
        },
    }


def main() -> int:
    try:
        schema, raw = read_last_row()
        ledger = normalize_row(schema, raw)
        role, path, result_data = choose_latest_result()
        report = {
            "system_result_intake_version": "v1",
            "current_ledger_event_id": ledger.get("event_id", ""),
            "current_ledger_task_id": ledger.get("task_id", ""),
            "current_ledger_state": ledger.get("state", ""),
            "latest_result_manifest": str(path.relative_to(ROOT)),
            "latest_result_ts": result_data.get("ts_utc", ""),
            **build_append_plan(role, result_data, ledger),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_result_intake_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
