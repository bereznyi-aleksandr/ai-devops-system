#!/usr/bin/env python3
"""Minimal canonical server-side ledger router.

Responsibilities:
- read the latest relevant event from governance/exchange_ledger.csv
- extract next_actor_role, next_expected_event, routing_decision_basis
- validate minimal transition integrity
- return a machine-readable routing result

Out of scope:
- governance decisions
- dispatch registry writes
- delivery execution
- mutation of ledger history
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REQUIRED_COLUMNS: List[str] = [
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
    "commit_sha",
]

ALLOWED_NEXT_ACTOR_VALUES = {
    "NONE",
    "ANALYST",
    "AUDITOR",
    "EXECUTOR",
    "LEDGER_WRITER",
    "LEDGER_ROUTER",
    "OPERATOR",
}

ALLOWED_NEXT_EVENT_VALUES = {
    "NONE",
    "TASK_PROPOSED",
    "PRE_ACTION_APPROVED",
    "ACTION_COMPLETED",
    "RESULT_ACCEPTED",
    "POST_ACTION_APPROVED",
    "TASK_CLOSED",
}


class LedgerRouterError(RuntimeError):
    """Router-specific failure."""


def read_rows(ledger_path: Path) -> List[Dict[str, str]]:
    if not ledger_path.exists():
        raise LedgerRouterError(f"Ledger file not found: {ledger_path}")

    with ledger_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        if header != REQUIRED_COLUMNS:
            raise LedgerRouterError("Ledger header mismatch. Expected canonical v151 columns.")
        return [
            {column: row.get(column, "") for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def select_latest_relevant_event(rows: List[Dict[str, str]], task_id: Optional[str]) -> Dict[str, str]:
    filtered = rows
    if task_id:
        filtered = [row for row in rows if row["task_id"] == task_id]
        if not filtered:
            raise LedgerRouterError(f"No events found for task_id: {task_id}")

    if not filtered:
        raise LedgerRouterError("Ledger has no events to route")

    return filtered[-1]


def validate_transition(event: Dict[str, str]) -> None:
    next_actor_role = event["next_actor_role"]
    next_expected_event = event["next_expected_event"]
    routing_decision_basis = event["routing_decision_basis"]

    if not next_actor_role:
        raise LedgerRouterError("next_actor_role is empty")
    if not next_expected_event:
        raise LedgerRouterError("next_expected_event is empty")
    if not routing_decision_basis:
        raise LedgerRouterError("routing_decision_basis is empty")

    if next_actor_role not in ALLOWED_NEXT_ACTOR_VALUES:
        raise LedgerRouterError(f"Unsupported next_actor_role: {next_actor_role}")
    if next_expected_event not in ALLOWED_NEXT_EVENT_VALUES:
        raise LedgerRouterError(f"Unsupported next_expected_event: {next_expected_event}")


def build_routing_result(event: Dict[str, str]) -> Dict[str, str]:
    return {
        "event_id": event["event_id"],
        "task_id": event["task_id"],
        "current_actor_role": event["actor_role"],
        "current_event_type": event["event_type"],
        "current_status": event["status"],
        "next_actor_role": event["next_actor_role"],
        "next_expected_event": event["next_expected_event"],
        "routing_decision_basis": event["routing_decision_basis"],
        "routing_status": "ROUTE_READY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read the latest relevant ledger event and return a machine-readable routing result."
    )
    parser.add_argument(
        "--ledger-path",
        default="governance/exchange_ledger.csv",
        help="Ledger CSV path relative to repo root or absolute path",
    )
    parser.add_argument(
        "--task-id",
        default="",
        help="Optional task_id filter. When omitted, routes from the latest ledger event.",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger_path).resolve()

    try:
        rows = read_rows(ledger_path)
        event = select_latest_relevant_event(rows, args.task_id or None)
        validate_transition(event)
        result = build_routing_result(event)
    except LedgerRouterError as exc:
        print(f"LEDGER_ROUTER_ERROR={exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
