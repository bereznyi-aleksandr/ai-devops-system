#!/usr/bin/env python3
import json
import os
from pathlib import Path

reports = Path("governance/reports")
transport = Path("governance/transport")
reports.mkdir(parents=True, exist_ok=True)
transport.mkdir(parents=True, exist_ok=True)

present = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
status = "secret_present" if present else "secret_missing"
blocker = None if present else {"code": "CLAUDE_CODE_OAUTH_TOKEN_MISSING"}

report = reports / "bem568_claude_token_secret_smoke.md"
report.write_text(
    f"# BEM-568 | Claude Token Secret Smoke | {status}\n\n"
    "Дата: workflow_runtime\n\n"
    "## Result\n"
    f"CLAUDE_CODE_OAUTH_TOKEN presence check: {status}\n\n"
    "## Security\n"
    "Token value was not printed.\n\n"
    "## Blocker\n"
    f"{json.dumps(blocker, ensure_ascii=False) if blocker else 'null'}\n",
    encoding="utf-8",
)

rec = {
    "record_type": "claude_token_secret_smoke",
    "cycle_id": "bem568-claude-token-secret-smoke",
    "source": "github-actions",
    "status": status,
    "artifact_path": str(report),
    "commit_sha": None,
    "blocker": blocker,
    "created_at": "workflow_runtime",
}
with (transport / "results.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(status)
