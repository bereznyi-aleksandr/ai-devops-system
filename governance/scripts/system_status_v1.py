#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "governance" / "exchange_ledger.csv"
RESULTS = ROOT / "governance" / "runtime" / "results"


class StatusError(RuntimeError):
    pass


def detect_schema(header: List[str]) -> str:
    if len(header) == 14 and header[0] == "schema_version" and header[1] == "event_id":
        return "14-col"
    if len(header) >= 27 and header[0] == "protocol_version" and header[1] == "event_id":
        return "27-col"
    raise StatusError("Unsupported ledger schema")


def read_ledger_tail() -> Tuple[str, Dict[str, str], int]:
    if not LEDGER.exists():
        raise StatusError("Missing governance/exchange_ledger.csv")
    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise StatusError("Ledger has no data rows")
    header = rows[0]
    schema = detect_schema(header)
    last = rows[-1]
    if len(last) != len(header):
        raise StatusError("Last ledger row length mismatch")
    return schema, dict(zip(header, last)), len(rows) - 1


def normalize(schema: str, row: Dict[str, str]) -> Dict[str, str]:
    if schema == "14-col":
        return {
            "protocol_version": row.get("schema_version", ""),
            "event_id": row.get("event_id", ""),
            "parent_event_id": row.get("parent_event_id", ""),
            "task_id": row.get("task_id", ""),
            "ts_utc": row.get("event_time", ""),
            "step_name": row.get("step_name", ""),
            "actor_role": row.get("actor_role", ""),
            "event_type": row.get("event_type", ""),
            "summary": row.get("description", ""),
            "state": row.get("status", ""),
            "next_role": row.get("next_actor_role", ""),
            "next_action": row.get("next_expected_event", ""),
            "artifact_ref": row.get("routing_decision_basis", ""),
            "commit_sha": row.get("commit_sha", ""),
        }
    return {
        "protocol_version": row.get("protocol_version", ""),
        "event_id": row.get("event_id", ""),
        "parent_event_id": row.get("parent_event_id", ""),
        "task_id": row.get("task_id", ""),
        "ts_utc": row.get("ts_utc", ""),
        "step_name": row.get("event_type", ""),
        "actor_role": row.get("actor_role", ""),
        "event_type": row.get("event_type", ""),
        "summary": row.get("summary", ""),
        "state": row.get("state", ""),
        "next_role": row.get("next_role", ""),
        "next_action": row.get("next_action", ""),
        "artifact_ref": row.get("artifact_ref", ""),
        "commit_sha": row.get("commit_sha", ""),
    }


def latest_result_manifest() -> Dict[str, str]:
    latest = None
    for name in ("executor_materialize_result.json", "auditor_materialize_result.json"):
        path = RESULTS / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = data.get("ts_utc", "")
        item = {
            "path": str(path.relative_to(ROOT)),
            "role": data.get("role", ""),
            "result": data.get("result", ""),
            "task_id": data.get("task_id", ""),
            "ts_utc": ts,
        }
        if latest is None or item["ts_utc"] > latest["ts_utc"]:
            latest = item
    return latest or {
        "path": "",
        "role": "",
        "result": "",
        "task_id": "",
        "ts_utc": "",
    }


def main() -> int:
    try:
        schema, raw, row_count = read_ledger_tail()
        tail = normalize(schema, raw)
        latest_result = latest_result_manifest()
        report = {
            "system_status_version": "v1",
            "result": "SUCCESS",
            "ledger_schema": schema,
            "ledger_row_count": row_count,
            "current_task_id": tail["task_id"],
            "current_state": tail["state"],
            "last_event_id": tail["event_id"],
            "last_event_type": tail["event_type"],
            "last_actor_role": tail["actor_role"],
            "last_event_time": tail["ts_utc"],
            "next_role": tail["next_role"],
            "next_action": tail["next_action"],
            "latest_artifact_ref": tail["artifact_ref"],
            "latest_commit_sha": tail["commit_sha"],
            "latest_result_manifest": latest_result,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_status_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
