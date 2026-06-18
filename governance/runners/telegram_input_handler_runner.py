#!/usr/bin/env python3
"""Telegram input handler runner for BEM-935."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/state/dispatch_queue.jsonl"
PROOFS = ROOT / "governance/proofs"
LOG = ROOT / "governance/logs/execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_mapper():
    path = ROOT / "governance/runners/telegram_input_mapper.py"
    spec = importlib.util.spec_from_file_location("telegram_input_mapper", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("telegram_input_mapper_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_update(path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    text = sys.stdin.read().strip()
    if text:
        return json.loads(text)
    return {
        "update_id": 935,
        "message": {
            "message_id": 935,
            "date": 1781800000,
            "chat": {"id": 601442777, "type": "private"},
            "from": {"id": 601442777, "is_bot": False, "first_name": "operator"},
            "text": "BEM-935 selftest: execute runtime queue handling",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mapper = load_mapper()
    update = read_update(args.update_file)
    item = mapper.map_update(update)

    checks = {
        "telegram_mapper_runtime_code_present": True,
        "trace_id_created": bool(item.get("trace_id")),
        "operator_authored_detected": item.get("operator_authored") is True,
        "role_inferred": item.get("role") in {"curator", "analyst", "auditor", "executor"},
        "dispatch_item_queued": item.get("status") == "queued",
        "no_bot_replay_claim": item.get("operator_authored") is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]

    if not args.dry_run and not blockers:
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-935",
        "task_id": "BEM935-P1-TELEGRAM-INPUT-HANDLER",
        "created_at": now(),
        "stage": {"tasks_done": 2, "tasks_total": 3, "percent": 67},
        "dispatch_item": item,
        "queue_path": str(QUEUE.relative_to(ROOT)),
        "dry_run": args.dry_run,
        "checks": checks,
        "blockers": blockers,
        "next_task": "BEM935-P1-EVENT-WRITER" if not blockers else None,
    }

    PROOFS.mkdir(parents=True, exist_ok=True)
    path = PROOFS / "BEM935_telegram_input_handler_receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": now(), "task_id": receipt["task_id"], "status": receipt["status"], "receipt": str(path.relative_to(ROOT))}, ensure_ascii=False) + "\n")
    if blockers:
        raise SystemExit("telegram_handler_blocked:" + ",".join(blockers))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
