#!/usr/bin/env python3
"""Map Telegram Bot API updates into BEM-935 dispatch queue items."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def iso_from_unix(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_text(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def infer_role(text: str) -> str:
    low = text.lower()
    if "audit" in low or "аудит" in low or "проверь" in low:
        return "auditor"
    if "execute" in low or "выполни" in low or "сделай" in low:
        return "executor"
    if "analy" in low or "анализ" in low:
        return "analyst"
    return "curator"


def extract_message(update: dict[str, Any]) -> dict[str, Any]:
    if "message" in update:
        return update["message"]
    if "edited_message" in update:
        return update["edited_message"]
    if "callback_query" in update and isinstance(update["callback_query"], dict):
        cq = update["callback_query"]
        msg = dict(cq.get("message") or {})
        msg["text"] = cq.get("data") or msg.get("text") or ""
        msg["from"] = cq.get("from") or msg.get("from") or {}
        return msg
    raise ValueError("telegram_update_has_no_message")


def map_update(update: dict[str, Any]) -> dict[str, Any]:
    message = extract_message(update)
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = safe_text(message.get("text") or message.get("caption") or "")
    message_id = message.get("message_id")
    chat_id = chat.get("id")
    date_iso = iso_from_unix(message.get("date"))
    trace_id = f"tg_{chat_id}_{message_id}_{date_iso.replace('-', '').replace(':', '').replace('Z', 'Z')}"
    role = infer_role(text)
    return {
        "dispatch_id": trace_id,
        "trace_id": trace_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "telegram",
        "operator_authored": bool(sender) and not bool(sender.get("is_bot")),
        "chat_id": chat_id,
        "message_id": message_id,
        "telegram_date": date_iso,
        "logical_role": role,
        "role": role,
        "provider": "claude_code",
        "payload": {
            "text": text,
            "chat": chat,
            "from": sender,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?")
    args = parser.parse_args()
    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    update = json.loads(raw)
    print(json.dumps(map_update(update), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
