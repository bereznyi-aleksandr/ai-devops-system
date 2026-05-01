#!/usr/bin/env python3
"""Minimal canonical server-side ledger writer.

Responsibilities:
- accept a validated event payload
- append exactly one event to governance/exchange_ledger.csv
- create a git commit for the append-only update
- bind the event commit SHA inside the written ledger row
- return the resulting commit SHA data

Out of scope:
- governance decisions
- routing / dispatch
- schema changes
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

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


class LedgerWriterError(RuntimeError):
    """Writer-specific failure."""


def run_git(args: List[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise LedgerWriterError(
            f"git {' '.join(args)} failed with code {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def load_payload(payload_path: Path) -> Dict[str, str]:
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LedgerWriterError(f"Failed to read payload JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise LedgerWriterError("Payload must be a JSON object")

    missing = [column for column in REQUIRED_COLUMNS if column not in payload]
    if missing:
        raise LedgerWriterError(f"Payload missing required fields: {', '.join(missing)}")

    normalized: Dict[str, str] = {}
    for column in REQUIRED_COLUMNS:
        value = payload.get(column, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            value = str(value)
        normalized[column] = value

    return normalized


def read_existing_rows(ledger_path: Path) -> List[Dict[str, str]]:
    if not ledger_path.exists():
        return []

    with ledger_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        if header != REQUIRED_COLUMNS:
            raise LedgerWriterError(
                "Ledger header mismatch. Expected canonical v151 columns."
            )
        return [
            {column: row.get(column, "") for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def ensure_unique_event_id(rows: List[Dict[str, str]], event_id: str) -> None:
    existing_event_ids = {row["event_id"] for row in rows}
    if event_id in existing_event_ids:
        raise LedgerWriterError(f"event_id already exists: {event_id}")


def write_rows_atomic(ledger_path: Path, rows: List[Dict[str, str]]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=str(ledger_path.parent),
    ) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = Path(temp_file.name)
    temp_path.replace(ledger_path)


def has_task_closed(rows: List[Dict[str, str]], task_id: str) -> bool:
    return any(
        row.get('task_id') == task_id and row.get('event_type') == 'TASK_CLOSED'
        for row in rows
    )


def append_event(ledger_path: Path, payload: Dict[str, str]) -> bool:
    rows = read_existing_rows(ledger_path)
    ensure_unique_event_id(rows, payload['event_id'])

    if payload.get('event_type') == 'TASK_CLOSED' and has_task_closed(rows, payload.get('task_id', '')):
        return False

    rows.append(payload)
    write_rows_atomic(ledger_path, rows)
    return True


def bind_commit_sha(ledger_path: Path, event_id: str, commit_sha: str) -> None:
    rows = read_existing_rows(ledger_path)
    updated = False
    for row in rows:
        if row["event_id"] == event_id:
            row["commit_sha"] = commit_sha
            updated = True
            break
    if not updated:
        raise LedgerWriterError(f"Unable to bind commit_sha. event_id not found: {event_id}")
    write_rows_atomic(ledger_path, rows)


def stage_ledger(repo_root: Path, ledger_path: Path) -> None:
    relative_path = ledger_path.relative_to(repo_root).as_posix()
    run_git(["add", relative_path], repo_root)


def commit_ledger_update(repo_root: Path, ledger_path: Path, commit_message: str) -> str:
    stage_ledger(repo_root, ledger_path)
    staged_paths = run_git(["diff", "--cached", "--name-only"], repo_root)
    if not staged_paths:
        raise LedgerWriterError("No staged changes found for ledger update")
    run_git(["commit", "-m", commit_message], repo_root)
    return run_git(["rev-parse", "HEAD"], repo_root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append one event to governance/exchange_ledger.csv, then bind commit_sha in a follow-up commit."
    )
    parser.add_argument("--payload-file", required=True, help="Path to event payload JSON")
    parser.add_argument(
        "--ledger-path",
        default="governance/exchange_ledger.csv",
        help="Ledger CSV path relative to repo root",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root where git commands should run",
    )
    parser.add_argument(
        "--commit-message",
        default="Update exchange ledger",
        help="Commit message for the append-only ledger update",
    )
    parser.add_argument(
        "--binding-commit-message",
        default="Bind commit sha in ledger row",
        help="Commit message for the follow-up commit that binds commit_sha inside the row",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    ledger_path = (repo_root / args.ledger_path).resolve()
    payload_path = Path(args.payload_file).resolve()

    try:
        payload = load_payload(payload_path)
        payload["commit_sha"] = ""
        appended = append_event(ledger_path, payload)
        if not appended:
            print('LEDGER_WRITER_SKIPPED_DUPLICATE_TASK_CLOSED')
            return 0
        event_commit_sha = commit_ledger_update(repo_root, ledger_path, args.commit_message)
        bind_commit_sha(ledger_path, payload["event_id"], event_commit_sha)
        binding_commit_sha = commit_ledger_update(repo_root, ledger_path, args.binding_commit_message)
    except LedgerWriterError as exc:
        print(f"LEDGER_WRITER_ERROR={exc}", file=sys.stderr)
        return 1

    print(f"LEDGER_PATH={ledger_path.relative_to(repo_root).as_posix()}")
    print(f"EVENT_ID={payload['event_id']}")
    print(f"TASK_ID={payload['task_id']}")
    print(f"EVENT_COMMIT_SHA={event_commit_sha}")
    print(f"BINDING_COMMIT_SHA={binding_commit_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
