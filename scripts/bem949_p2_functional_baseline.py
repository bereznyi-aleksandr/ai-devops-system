#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "governance/proofs/BEM949_p2_functional_baseline.json"
REPORT = ROOT / "governance/reports/BEM949_p2_functional_before_after.md"
TARGETS = [
    ".github/workflows/bem934-binding-failure-log-inspector.yml",
    ".github/workflows/bem931-v36-release-repair-gate.yml",
    ".github/workflows/bem947-live-object-dispatch-retry.yml",
    ".github/workflows/bem948-live-object-e2e.yml",
    ".github/workflows/bem948-p0-claude-diagnostic-retry.yml",
]

def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""

def main():
    rows = []
    for path in TARGETS:
        exists = (ROOT / path).is_file()
        history = git("log", "--all", "--format=%H", "--", path).splitlines()
        rows.append({
            "path": path,
            "exists": exists,
            "current_blob_sha": git("hash-object", path) if exists else None,
            "current_blob_sha_type": "git_blob",
            "historical_candidate_commit_sha": history[1] if len(history) > 1 else None,
            "historical_candidate_commit_sha_type": "commit",
        })
    payload = {
        "schema_version": 2,
        "protocol": "BEM-949",
        "task_id": "BEM949-P2-FUNCTIONAL-RESTORE",
        "receipt_id": "BEM949_p2_functional_baseline",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "OBSERVED",
        "head_sha": git("rev-parse", "HEAD"),
        "head_sha_type": "commit",
        "workflows": rows,
        "checks": {
            "all_five_audited_workflows_enumerated": len(rows) == 5,
            "current_blob_sha_types_explicit": True,
            "historical_candidates_searched": True,
            "functional_restore_claimed": False,
        },
        "non_claim": "Baseline only; no workflow completion or provider-success claim.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    table = ["# BEM-949 P2 baseline", "", "| Workflow | Current blob | Historical candidate |", "|---|---|---|"]
    for row in rows:
        table.append(f"| `{row['path']}` | `{row['current_blob_sha']}` | `{row['historical_candidate_commit_sha'] or 'not found'}` |")
    REPORT.write_text("\n".join(table) + "\n", encoding="utf-8")
    if not OUT.is_file() or not REPORT.is_file():
        raise RuntimeError("baseline artifacts missing")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
