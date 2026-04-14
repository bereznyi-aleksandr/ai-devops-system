#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "governance" / "exchange_ledger.csv"
INTAKE = ROOT / "governance" / "scripts" / "system_result_intake_v1.py"


class LedgerWriterError(RuntimeError):
    pass


def run_intake() -> dict:
    proc = subprocess.run(
        [sys.executable, str(INTAKE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise LedgerWriterError(proc.stderr.strip() or proc.stdout.strip() or "system_result_intake_v1 failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise LedgerWriterError(f"Intake output is not valid JSON: {e}") from e


def read_ledger_rows() -> List[List[str]]:
    if not LEDGER.exists():
        raise LedgerWriterError("Missing governance/exchange_ledger.csv")
    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def main() -> int:
    try:
        intake = run_intake()
        plan = intake.get("ledger_append_plan") or {}
        schema = plan.get("schema", "")
        header_order = plan.get("header_order") or []
        proposed_row = plan.get("proposed_row") or []

        if schema != "14-col":
            raise LedgerWriterError(f"Unsupported append schema: {schema}")

        rows = read_ledger_rows()
        header = rows[0]
        existing = rows[1:]

        if header != header_order:
            raise LedgerWriterError("Ledger header does not match intake header_order")

        if len(proposed_row) != len(header):
            raise LedgerWriterError(
                f"Proposed row length {len(proposed_row)} does not match ledger header length {len(header)}"
            )

        proposed_event_id = proposed_row[1]
        if not proposed_event_id:
            raise LedgerWriterError("Proposed row has empty event_id")

        existing_event_ids = {row[1] for row in existing if len(row) > 1}
        if proposed_event_id in existing_event_ids:
            raise LedgerWriterError(f"Duplicate event_id already exists in ledger: {proposed_event_id}")

        with LEDGER.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(proposed_row)

        result = {
            "system_ledger_writer_version": "v1",
            "result": "SUCCESS",
            "written_event_id": proposed_event_id,
            "written_task_id": proposed_row[3],
            "written_status": proposed_row[9],
            "written_next_role": proposed_row[10],
            "written_next_action": proposed_row[11],
            "ledger_path": str(LEDGER.relative_to(ROOT)),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_ledger_writer_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
