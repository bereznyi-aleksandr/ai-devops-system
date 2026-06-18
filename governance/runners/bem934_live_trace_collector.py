#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

TRACE = "tg_934432449"
OUT = Path("governance/proofs/BEM934_live_trace_collector.json")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def file_evidence(path: Path) -> dict:
    rel = path.as_posix()
    return {
        "path": rel,
        "size": path.stat().st_size,
        "blob_sha": git("rev-parse", f"HEAD:{rel}"),
        "last_commit_sha": git("log", "-1", "--format=%H", "--", rel),
    }


def main() -> None:
    found = []
    bases = [
        Path("governance/proofs"),
        Path("governance/reports"),
        Path("governance/transport"),
        Path("governance/state"),
        Path("governance/codex/results"),
    ]
    for base in bases:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if TRACE not in text:
                continue
            entry = file_evidence(path)
            entry["json_parseable"] = False
            entry["status"] = None
            entry["provider_selected"] = None
            entry["target_workflow"] = None
            try:
                data = json.loads(text)
                entry["json_parseable"] = True
                if isinstance(data, dict):
                    entry["status"] = data.get("status")
                    entry["provider_selected"] = data.get("provider_selected")
                    entry["target_workflow"] = (
                        data.get("target_workflow_id")
                        or data.get("target_workflow")
                        or data.get("workflow_id")
                    )
            except json.JSONDecodeError:
                pass
            found.append(entry)

    out = {
        "task_id": "BEM934-LIVE-TEST",
        "trace_id": TRACE,
        "head_sha": git("rev-parse", "HEAD"),
        "artifacts": found,
        "checks": {
            "trace_materialized": bool(found),
            "router_receipt_present": any("provider_router" in e["path"] for e in found),
            "claude_report_present": any(
                e["path"].startswith("governance/reports/") for e in found
            ),
            "transport_result_present": any(
                e["path"] == "governance/transport/results.jsonl" for e in found
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
