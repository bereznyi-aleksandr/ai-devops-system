#!/usr/bin/env python3
"""Pick one queued Telegram outbox message.

GATE-5 compatibility:
- legacy queue: governance/telegram_outbox.jsonl
- canonical queue: governance/telegram/outbox.jsonl
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OUTBOXES = [
    Path("governance/telegram_outbox.jsonl"),
    Path("governance/telegram/outbox.jsonl"),
]
TRANSPORT = Path("governance/transport/results.jsonl")
PICK = Path("governance/tmp/telegram_pick.json")
CURRENT = Path("governance/state/operator_progress_current.json")


def load_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append((line_no, item))
    return rows


def stable_hash(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"sha256_{digest}_len_{len(text)}"


def delivered(source_path: str, line_no: int, msg_hash: str) -> bool:
    for _, rec in load_jsonl(TRANSPORT):
        if rec.get("record_type") != "telegram_delivery_result":
            continue
        if rec.get("status") not in ["sent", "sent_synthetic"]:
            continue
        same_hash = rec.get("message_hash") == msg_hash
        same_line = rec.get("outbox_line") == line_no
        same_source = not rec.get("outbox_path") or rec.get("outbox_path") == source_path
        if same_hash and same_line and same_source:
            return True
    return False


def current_bem() -> str:
    if not CURRENT.exists():
        return ""
    try:
        return str(json.loads(CURRENT.read_text(encoding="utf-8")).get("bem", ""))
    except Exception:
        return ""


def message_text(rec: dict[str, Any]) -> str:
    return str(rec.get("message") or rec.get("text") or "").strip()


def priority(rec: dict[str, Any]) -> int:
    cycle = str(rec.get("cycle_id", ""))
    msg = message_text(rec)
    bem = current_bem()
    score = 0
    if rec.get("priority") == "operator_progress":
        score += 1000
    if bem and bem in msg:
        score += 500
    if cycle.startswith("bem550") or "BEM-550" in msg:
        score += 400
    if rec.get("status") == "ready_to_send":
        score += 100
    if "BEM-540" in msg or "synthetic" in msg.lower():
        score -= 300
    if rec.get("canonical") is True:
        score += 10
    if str(rec.get("task_id", "")) == "GATE-5":
        score += 50
    return score


candidates: list[tuple[int, str, int, dict[str, Any], str]] = []
for outbox_path in OUTBOXES:
    for line_no, rec in load_jsonl(outbox_path):
        if rec.get("status") not in ["ready_to_send", "queued_for_sender", "queued"]:
            continue
        message = message_text(rec)
        if not message:
            continue
        msg_hash = stable_hash(message)
        source = str(outbox_path)
        if delivered(source, line_no, msg_hash):
            continue
        candidates.append((priority(rec), source, line_no, rec, msg_hash))

if candidates:
    candidates.sort(key=lambda item: (item[0], item[2]))
    score, source, line_no, rec, msg_hash = candidates[-1]
    pick = {
        "found": True,
        "outbox_path": source,
        "outbox_line": line_no,
        "cycle_id": rec.get("cycle_id", "telegram-outbox-live"),
        "message": message_text(rec),
        "message_hash": msg_hash,
        "priority": score,
    }
else:
    pick = {"found": False}

PICK.parent.mkdir(parents=True, exist_ok=True)
PICK.write_text(json.dumps(pick, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(pick, ensure_ascii=False))
