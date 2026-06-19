#!/usr/bin/env python3
"""Foundation validator runtime for BEM-941."""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
STATE = ROOT / "governance" / "state"
TARGETS = [
    "AGENT_CONTEXT.md",
    "governance/roadmap/ACTIVE_QUEUE.json",
    "governance/config/provider_config.json",
    "governance/runners/curator_router.py",
    "governance/runners/dispatch_consumer.py",
    "governance/runners/object_runner.py",
    "governance/runners/role_report_writer.py",
    "governance/runners/provider_activation.py",
]
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def validate():
    results = {}
    for item in TARGETS:
        path = ROOT / item
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        results[item] = {"exists": path.exists(), "size": len(text.encode("utf-8")), "not_stub": len(text.encode("utf-8")) > 300 if item.endswith(".py") else True}
    checks = {
        "agent_context_exists": results["AGENT_CONTEXT.md"]["exists"],
        "active_queue_exists": results["governance/roadmap/ACTIVE_QUEUE.json"]["exists"],
        "provider_config_exists": results["governance/config/provider_config.json"]["exists"],
        "critical_runners_not_stub": all(results[x]["not_stub"] for x in results if x.endswith(".py")),
    }
    blockers = [k for k,v in checks.items() if not v]
    return {"status":"PASS" if not blockers else "BLOCKED", "protocol":"BEM-941", "task_id":"BEM941-P1-FOUNDATION-VALIDATOR", "created_at":now(), "stage":{"tasks_done":2,"tasks_total":4,"percent":50}, "results":results, "checks":checks, "blockers":blockers, "next_task":"BEM941-P2-TESTING-CONTOUR-ASSIGNMENT" if not blockers else None}
def main():
    receipt = validate()
    PROOFS.mkdir(parents=True, exist_ok=True); STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "foundation_validation_state.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    (PROOFS / "BEM941_foundation_validator_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt["status"] != "PASS": raise SystemExit(1)
if __name__ == "__main__": main()
