#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "governance"
PROTOCOL = GOV / "PROTOCOL.md"
LEDGER = GOV / "exchange_ledger.csv"
RUNTIME = GOV / "runtime"
PACKETS = RUNTIME / "packets"
RESULTS = RUNTIME / "results"
SCRIPTS = GOV / "scripts"

REQUIRED_SCRIPTS = [
    "system_router_v1.py",
    "system_packet_writer_v1.py",
    "system_role_launcher_v2.py",
    "system_result_intake_v1.py",
    "system_ledger_writer_v1.py",
    "system_orchestrator_v1.py",
]

REQUIRED_RUNNERS = [
    "run_executor_codex_v2.sh",
    "run_auditor_codex_v1.sh",
]

REQUIRED_RUNTIME_FILES = [
    "packets/executor_packet_current.json",
    "packets/auditor_packet_current.json",
    "results/executor_materialize_result.json",
    "results/auditor_materialize_result.json",
]


class HealthError(RuntimeError):
    pass


def read_protocol_version() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    m = re.search(r"##\s*Версия:\s*([^\s]+)", text)
    if not m:
        raise HealthError("Could not parse protocol version from governance/PROTOCOL.md")
    return m.group(1).strip()


def read_ledger() -> Tuple[List[str], List[List[str]]]:
    if not LEDGER.exists():
        raise HealthError("Missing governance/exchange_ledger.csv")
    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise HealthError("Ledger has no data rows")
    return rows[0], rows[1:]


def detect_schema(header: List[str]) -> str:
    if len(header) == 14 and header[0] == "schema_version" and header[1] == "event_id":
        return "14-col"
    if len(header) >= 27 and header[0] == "protocol_version" and header[1] == "event_id":
        return "27-col"
    raise HealthError("Unsupported ledger schema")


def check_required_paths() -> Tuple[List[str], List[str]]:
    ok, missing = [], []
    for rel in REQUIRED_SCRIPTS + REQUIRED_RUNNERS:
        p = SCRIPTS / rel
        (ok if p.exists() else missing).append(str(p.relative_to(ROOT)))
    for rel in REQUIRED_RUNTIME_FILES:
        p = GOV / "runtime" / rel.split('/', 1)[1] if rel.startswith('runtime/') else RUNTIME / rel.split('/', 1)[1] if '/' in rel else RUNTIME / rel
        # Normalize based on declared paths above.
        if rel.startswith("packets/"):
            p = PACKETS / rel.split("/", 1)[1]
        elif rel.startswith("results/"):
            p = RESULTS / rel.split("/", 1)[1]
        (ok if p.exists() else missing).append(str(p.relative_to(ROOT)))
    return ok, missing


def load_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        protocol_version = read_protocol_version()
        header, rows = read_ledger()
        schema = detect_schema(header)
        last = rows[-1]
        ok_paths, missing_paths = check_required_paths()

        issues: List[str] = []
        notes: List[str] = []

        if schema == "14-col":
            last_protocol = last[0]
            last_event_id = last[1]
            last_task_id = last[3]
            last_status = last[9]
            last_next_role = last[10]
            last_next_action = last[11]
        else:
            idx = {name: i for i, name in enumerate(header)}
            last_protocol = last[idx["protocol_version"]]
            last_event_id = last[idx["event_id"]]
            last_task_id = last[idx["task_id"]]
            last_status = last[idx["state"]]
            last_next_role = last[idx["next_role"]]
            last_next_action = last[idx["next_action"]]

        if last_protocol != protocol_version:
            issues.append(
                f"Ledger/protocol version mismatch: ledger={last_protocol!r}, protocol={protocol_version!r}"
            )

        if missing_paths:
            issues.append(f"Missing required paths: {', '.join(missing_paths)}")

        executor_result = load_json_if_exists(RESULTS / "executor_materialize_result.json")
        auditor_result = load_json_if_exists(RESULTS / "auditor_materialize_result.json")

        if executor_result and executor_result.get("protocol_version") not in ("", protocol_version):
            issues.append("executor_materialize_result.json protocol_version mismatch")
        if auditor_result and auditor_result.get("protocol_version") not in ("", protocol_version):
            issues.append("auditor_materialize_result.json protocol_version mismatch")

        if last_next_role not in ("EXECUTOR", "AUDITOR", "", "SYSTEM"):
            issues.append(f"Unexpected next role in ledger tail: {last_next_role}")
        if not last_event_id:
            issues.append("Last ledger row has empty event_id")
        if not last_task_id:
            issues.append("Last ledger row has empty task_id")

        notes.append(f"Last ledger event: {last_event_id}")
        notes.append(f"Last ledger task: {last_task_id}")
        notes.append(f"Last ledger status: {last_status}")
        notes.append(f"Last route: {last_next_role} / {last_next_action}")
        notes.append(f"Ledger rows: {len(rows)}")

        report = {
            "system_health_check_version": "v1",
            "result": "HEALTHY" if not issues else "ATTENTION",
            "protocol_version": protocol_version,
            "ledger_schema": schema,
            "last_event_id": last_event_id,
            "last_task_id": last_task_id,
            "last_status": last_status,
            "last_next_role": last_next_role,
            "last_next_action": last_next_action,
            "checked_paths_count": len(ok_paths) + len(missing_paths),
            "missing_paths": missing_paths,
            "issues": issues,
            "notes": notes,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not issues else 2
    except Exception as e:
        print(json.dumps({
            "system_health_check_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
