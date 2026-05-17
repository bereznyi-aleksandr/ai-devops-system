#!/usr/bin/env python3
import json
import os
from pathlib import Path

TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
STATUS = "secret_present" if TOKEN else "secret_missing"
BLOCKER = None if TOKEN else {"code": "CLAUDE_CODE_OAUTH_TOKEN_MISSING"}

reports_dir = Path("governance/reports")
transport_dir = Path("governance/transport")
reports_dir.mkdir(parents=True, exist_ok=True)
transport_dir.mkdir(parents=True, exist_ok=True)

report_path = reports_dir / "bem568_claude_token_secret_smoke.md"
lines = [
    "# BEM-568 | Claude Token Secret Smoke | " + STATUS,
    "",
    "Дата: workflow_runtime",
    "",
    "## Result",
    "CLAUDE_CODE_OAUTH_TOKEN presence check: " + STATUS,
    "",
    "## Security",
    "Token value was not printed.",
    "",
    "## Blocker",
    "null" if BLOCKER is None else json.dumps(BLOCKER, ensure_ascii=False),
    "",
]
report_path.write_text("\n".join(lines), encoding="utf-8")

record = {
    "record_type": "claude_token_secret_smoke",
    "cycle_id": "bem568-claude-token-secret-smoke",
    "source": "github-actions",
    "status": STATUS,
    "artifact_path": str(report_path),
    "commit_sha": None,
    "blocker": BLOCKER,
    "created_at": "workflow_runtime",
}
with (transport_dir / "results.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("CLAUDE_CODE_OAUTH_TOKEN presence check:", STATUS)
