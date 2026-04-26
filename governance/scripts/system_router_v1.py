#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "governance" / "exchange_ledger.csv"
PROTOCOL = ROOT / "governance" / "PROTOCOL.md"
EXECUTOR_PACKET = ROOT / "governance" / "runtime" / "packets" / "executor_packet_current.json"
AUDITOR_PACKET = ROOT / "governance" / "runtime" / "packets" / "auditor_packet_current.json"

CANONICAL_LEDGER_SCHEMA = "27-col"
CANONICAL_LEDGER_HEADER = [
    "event_id",
    "parent_event_id",
    "task_id",
    "ts_utc",
    "actor_role",
    "event_type",
    "state",
    "decision",
    "result",
    "summary",
    "artifact_ref",
    "proof_ref",
    "ci_ref",
    "log_ref",
    "error_class",
    "error_details",
    "next_role",
    "next_action",
    "protocol_version",
    "commit_sha",
    "stall_class",
    "infra_scope",
    "causation_id",
    "correlation_id",
    "idempotency_key",
    "producer",
    "producer_run_id",
]


class RouterError(RuntimeError):
    pass


def read_protocol_version() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith("Версия:"):
            value = stripped.split(":", 1)[1].strip()
            match = re.search(r"v\d+\.\d+(?:-[A-Z0-9]+)?", value)
            if match:
                return match.group(0)
            return value.split()[0]
    raise RouterError("Could not determine protocol version from governance/PROTOCOL.md")


def detect_ledger_schema(header: List[str]) -> str:
    if header == CANONICAL_LEDGER_HEADER:
        return CANONICAL_LEDGER_SCHEMA
    raise RouterError(
        "Unsupported ledger schema: expected canonical 27-col header; "
        f"found {len(header)} columns: {','.join(header)}"
    )


def read_last_row() -> Tuple[str, Dict[str, str]]:
    if not LEDGER.exists():
        raise RouterError("Missing governance/exchange_ledger.csv")

    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise RouterError("Ledger has no data rows")

    header = rows[0]
    schema = detect_ledger_schema(header)
    last = rows[-1]
    if len(last) != len(header):
        raise RouterError("Last ledger row does not match header length")

    return schema, dict(zip(header, last))


def normalize_row(schema: str, row: Dict[str, str]) -> Dict[str, str]:
    if schema != CANONICAL_LEDGER_SCHEMA:
        raise RouterError(f"Unsupported ledger schema: {schema}")
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
        "proof_ref": row.get("proof_ref", ""),
        "ci_ref": row.get("ci_ref", ""),
        "log_ref": row.get("log_ref", ""),
        "commit_sha": row.get("commit_sha", ""),
    }


def packet_plan(n: Dict[str, str]) -> Dict[str, object]:
    next_role = n["next_role"]
    next_action = n["next_action"]
    task_id = n["task_id"]
    event_id = n["event_id"]
    artifact_ref = n.get("artifact_ref", "")
    protocol_version = n["protocol_version"]

    if next_role == "EXECUTOR":
        return {
            "packet_path": str(EXECUTOR_PACKET.relative_to(ROOT)),
            "role": "EXECUTOR",
            "packet": {
                "protocol_version": protocol_version,
                "runtime": "GitHub Codespaces",
                "role": "EXECUTOR",
                "input_event_id": event_id,
                "parent_event_id": event_id,
                "task_id": task_id,
                "current_state": n["state"],
                "next_role": "EXECUTOR",
                "next_action": next_action,
                "artifact_ref": artifact_ref,
                "proof_ref": n.get("proof_ref", ""),
                "ci_ref": n.get("ci_ref", ""),
                "log_ref": n.get("log_ref", ""),
                "summary": f"SYSTEM router generated EXECUTOR packet for {task_id} / {next_action}.",
                "constraints": [
                    "Do not write governance/exchange_ledger.csv",
                    "Do not merge",
                    "Write only one allowed artifact",
                    "Write executor_materialize_result.json",
                ],
            },
        }

    if next_role == "AUDITOR":
        decision_id = f"AUDIT-{task_id}-AUTO-0001"
        return {
            "packet_path": str(AUDITOR_PACKET.relative_to(ROOT)),
            "role": "AUDITOR",
            "packet": {
                "protocol_version": protocol_version,
                "runtime": "GitHub Codespaces",
                "role": "AUDITOR",
                "input_event_id": event_id,
                "parent_event_id": event_id,
                "task_id": task_id,
                "current_state": n["state"],
                "next_role": "AUDITOR",
                "next_action": next_action,
                "decision_id": decision_id,
                "reviewed_ref": artifact_ref,
                "reviewed_commit_sha": n.get("commit_sha", ""),
                "artifact_ref": artifact_ref,
                "proof_ref": n.get("proof_ref", ""),
                "ci_ref": n.get("ci_ref", ""),
                "log_ref": n.get("log_ref", ""),
                "summary": f"SYSTEM router generated AUDITOR packet for {task_id} / {next_action}.",
                "constraints": [
                    "Do not write governance/exchange_ledger.csv",
                    "Do not merge",
                    "Do not implement product changes",
                    "Write only one allowed decision artifact",
                    "Write auditor_materialize_result.json",
                ],
            },
        }

    raise RouterError(f"Unsupported next_role: {next_role}")


def main() -> int:
    try:
        protocol_version = read_protocol_version()
        schema, row = read_last_row()
        n = normalize_row(schema, row)

        if n["protocol_version"] != protocol_version:
            raise RouterError(
                f"Protocol mismatch: ledger row has {n['protocol_version']}, protocol file has {protocol_version}"
            )

        plan = packet_plan(n)
        report = {
            "system_router_version": "v1",
            "ledger_schema": schema,
            "protocol_version": protocol_version,
            "current_event_id": n["event_id"],
            "current_task_id": n["task_id"],
            "current_state": n["state"],
            "current_event_type": n["event_type"],
            "next_role": n["next_role"],
            "next_action": n["next_action"],
            "artifact_ref": n["artifact_ref"],
            "suggested_packet_path": plan["packet_path"],
            "suggested_packet": plan["packet"],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(
            json.dumps(
                {
                    "system_router_version": "v1",
                    "result": "BLOCKED",
                    "error": str(e),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
