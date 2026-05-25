#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
REQUEST = ROOT / "governance/audit/mailbox/to_curator/BEM859_PROTOCOL_ALIGNMENT_REQUEST_FOR_CURATOR.md"
CLAUDE_TASK = ROOT / "governance/tasks/pending/CLAUDE_INTERNAL_AUDIT_BEM859.md"
RESPONSE = ROOT / "governance/audit/mailbox/from_claude/BEM859_PROTOCOL_ALIGNMENT_RESPONSE.md"
STATE = ROOT / "governance/runtime/curator_dispatch/BEM863_CURATOR_CLAUDE_ROUTE.md"
EVENTS = ROOT / "governance/events/bem863_curator_claude_dispatch.jsonl"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event(obj):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    obj["timestamp"] = obj.get("timestamp") or now()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    ts = now()
    if not REQUEST.exists():
        event({"event": "BEM863_NO_CURATOR_REQUEST", "request": str(REQUEST)})
        return 0
    request_text = REQUEST.read_text(encoding="utf-8")
    RESPONSE.parent.mkdir(parents=True, exist_ok=True)
    if not RESPONSE.exists():
        RESPONSE.write_text("# BEM-859 CLAUDE AUDIT RESPONSE MAILBOX\nStatus: PENDING_CLAUDE_RESPONSE\nAllowed: APPROVED | APPROVED_WITH_AMENDMENTS | BLOCKED_WITH_REASON\n", encoding="utf-8")
    CLAUDE_TASK.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_TASK.write_text(f"# CLAUDE INTERNAL AUDIT — BEM-859\nStatus: PENDING_CLAUDE_AUDIT\nCreated: {ts}\nRoute: GPT -> Curator -> Claude -> mailbox -> GPT\nResponse mailbox: governance/audit/mailbox/from_claude/BEM859_PROTOCOL_ALIGNMENT_RESPONSE.md\n\n## Task\nReview the protocol draft and write exactly one final status to the response mailbox:\n- APPROVED\n- APPROVED_WITH_AMENDMENTS\n- BLOCKED_WITH_REASON\n\n## Curator request snapshot\n{request_text}\n", encoding="utf-8")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(f"# BEM-863 Curator Claude route\nStatus: ACTIVE\nUpdated: {ts}\nRequest: {REQUEST}\nClaude task: {CLAUDE_TASK}\nResponse mailbox: {RESPONSE}\n", encoding="utf-8")
    event({"event": "BEM863_CLAUDE_TASK_DISPATCHED", "task": str(CLAUDE_TASK), "response": str(RESPONSE)})
    print("BEM863_CLAUDE_TASK_DISPATCHED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
