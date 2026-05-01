#!/usr/bin/env python3
"""Minimal working canonical append-only ledger writer for PROTOCOL v3.6-RC2.

This writer is intentionally narrow:
- reads one JSON payload;
- validates canonical header and required fields;
- creates canonical ledger if missing;
- rejects duplicate event_id;
- rejects duplicate logical action by (correlation_id, idempotency_key, actor_role, event_type);
- appends exactly one row.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

CANONICAL_COLUMNS: List[str] = [
    'event_id','parent_event_id','task_id','ts_utc','actor_role','event_type','state','decision','result','summary',
    'artifact_ref','proof_ref','ci_ref','log_ref','error_class','error_details','next_role','next_action',
    'protocol_version','commit_sha','stall_class','infra_scope','causation_id','correlation_id','idempotency_key',
    'producer','producer_run_id'
]

REQUIRED_NON_EMPTY_FIELDS: List[str] = [
    'event_id','task_id','ts_utc','actor_role','event_type','state','summary','next_role','next_action',
    'protocol_version','causation_id','correlation_id','idempotency_key','producer','producer_run_id'
]

ALLOWED_PROTOCOL_VERSION = 'v3.6-RC2'


class AppendLedgerRowError(RuntimeError):
    pass


def normalize_value(value: object) -> str:
    if value is None:
        return ''
    return value if isinstance(value, str) else str(value)


def load_payload(payload_path: Path) -> Dict[str, str]:
    try:
        payload = json.loads(payload_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise AppendLedgerRowError(f'Failed to read payload JSON: {exc}') from exc

    if not isinstance(payload, dict):
        raise AppendLedgerRowError('Payload must be a JSON object')

    missing = [column for column in CANONICAL_COLUMNS if column not in payload]
    if missing:
        raise AppendLedgerRowError(f"Payload missing required fields: {', '.join(missing)}")

    normalized: Dict[str, str] = {column: normalize_value(payload.get(column, '')) for column in CANONICAL_COLUMNS}

    if normalized['protocol_version'] != ALLOWED_PROTOCOL_VERSION:
        raise AppendLedgerRowError(f'protocol_version must be {ALLOWED_PROTOCOL_VERSION}')

    empty_required = [field for field in REQUIRED_NON_EMPTY_FIELDS if not normalized[field].strip()]
    if empty_required:
        raise AppendLedgerRowError(f"Required fields must be non-empty: {', '.join(empty_required)}")

    return normalized


def initialize_empty_ledger(ledger_path: Path) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()


def read_existing_rows(ledger_path: Path) -> List[Dict[str, str]]:
    if not ledger_path.exists():
        initialize_empty_ledger(ledger_path)
        return []

    with ledger_path.open('r', encoding='utf-8', newline='') as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        if header != CANONICAL_COLUMNS:
            raise AppendLedgerRowError('Ledger header mismatch. Expected canonical v3.6-RC2 columns.')
        return [{column: normalize_value(row.get(column, '')) for column in CANONICAL_COLUMNS} for row in reader]


def ensure_event_uniqueness(rows: List[Dict[str, str]], payload: Dict[str, str]) -> None:
    event_id = payload['event_id']
    if any(row['event_id'] == event_id for row in rows):
        raise AppendLedgerRowError(f'event_id already exists: {event_id}')


def ensure_logical_idempotency(rows: List[Dict[str, str]], payload: Dict[str, str]) -> None:
    idem = payload['idempotency_key']
    correlation = payload['correlation_id']
    actor = payload['actor_role']
    event_type = payload['event_type']
    for row in rows:
        if (
            row.get('idempotency_key', '') == idem
            and row.get('correlation_id', '') == correlation
            and row.get('actor_role', '') == actor
            and row.get('event_type', '') == event_type
        ):
            raise AppendLedgerRowError('Duplicate logical action detected by idempotency contour')


def write_rows_atomic(ledger_path: Path, rows: List[Dict[str, str]]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', delete=False, dir=str(ledger_path.parent)) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = Path(temp_file.name)
    temp_path.replace(ledger_path)


def append_event(ledger_path: Path, payload: Dict[str, str]) -> None:
    rows = read_existing_rows(ledger_path)
    ensure_event_uniqueness(rows, payload)
    ensure_logical_idempotency(rows, payload)
    rows.append(payload)
    write_rows_atomic(ledger_path, rows)


def main() -> int:
    parser = argparse.ArgumentParser(description='Append one event row to the canonical v3.6-RC2 ledger')
    parser.add_argument('--payload-file', required=True, help='Path to event payload JSON')
    parser.add_argument('--ledger-path', default='governance/exchange_ledger_v3_6_rc2.csv', help='Canonical ledger CSV path')
    args = parser.parse_args()

    payload_path = Path(args.payload_file).resolve()
    ledger_path = Path(args.ledger_path).resolve()

    try:
        payload = load_payload(payload_path)
        append_event(ledger_path, payload)
    except AppendLedgerRowError as exc:
        print(f'APPEND_LEDGER_ROW_ERROR={exc}', file=sys.stderr)
        return 1

    print(f'LEDGER_PATH={ledger_path}')
    print(f"EVENT_ID={payload['event_id']}")
    print(f"TASK_ID={payload['task_id']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
