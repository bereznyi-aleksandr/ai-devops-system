#!/usr/bin/env python3
"""Canonical v3.6-RC2 ledger writer entrypoint.
Temporary minimal implementation for new autonomous contour bootstrap.
"""

CANONICAL_COLUMNS = [
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

if __name__ == "__main__":
    print("append_ledger_row.py bootstrap created")
