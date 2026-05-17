#!/usr/bin/env python3
import json
import os
from pathlib import Path

token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
status = "secret_present" if token else "secret_missing"
blocker = None if token else {"code": "CLAUDE_CODE_OAUTH_TOKEN_MISSING"}

Path("governance/reports").mkdir(parents=True, exist_ok=True)
Path("governance/transport").mkdir(parents=True, exist_ok=True)

report = Path("governance/reports/bem568_claude_token_secret_smoke.md")
report.write_text(
    "# BEM-568 | Claude Token Secret Smoke | " + status + "

"
    "Дата: workflow_runtime

"
    "## Result
"
    "CLAUDE_CODE_OAUTH_TOKEN presence check: " + status + "

"
    "## Security
"
    "Token value was not printed.

"
    "## Blocker
"
    + ("null" if blocker is None else json.dumps(blocker, ensure_ascii=False)) + "
",
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
with Path("governance/transport/results.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "
")
print("CLAUDE_CODE_OAUTH_TOKEN presence check:", status)

# BEM-568 auto-run marker: push trigger enabled for safe secret presence smoke.
