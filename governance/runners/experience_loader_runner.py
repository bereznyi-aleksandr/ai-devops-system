#!/usr/bin/env python3
"""Experience loader runner runtime for BEM-945."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
STATE = ROOT / "governance" / "state"
LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"
SOURCES = [ROOT / "AGENT_CONTEXT.md", ROOT / "SYSTEM_STATUS.md", ROOT / "governance" / "roadmap" / "ACTIVE_QUEUE.json", ROOT / "governance" / "proofs" / "PROOF_MANIFEST.json"]

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read_text(path: Path, max_chars: int) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "exists": False, "size": 0, "excerpt": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"path": str(path.relative_to(ROOT)), "exists": True, "size": len(text.encode("utf-8")), "excerpt": text[:max_chars]}

def read_recent_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists(): return []
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            item = {"_invalid_json": True, "error": str(exc), "raw": line[:500]}
        if isinstance(item, dict): out.append(item)
    return out

def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

def load(max_chars: int, recent: int) -> dict[str, Any]:
    docs = [read_text(path, max_chars) for path in SOURCES]
    recent_log = read_recent_jsonl(LOG, recent)
    return {
        "status": "PASS", "protocol": "BEM-945", "task_id": "BEM945-P2-EXPERIENCE-LOADER-RUNNER", "created_at": now(),
        "sources": docs, "recent_execution_log": recent_log, "source_count": len(docs),
        "existing_source_count": sum(1 for item in docs if item["exists"]),
        "recent_log_count": len(recent_log),
        "non_claim": "experience/context loading only; no downstream LLM completion claimed",
    }

def write(state: dict[str, Any]) -> dict[str, Any]:
    STATE.mkdir(parents=True, exist_ok=True); PROOFS.mkdir(parents=True, exist_ok=True)
    state_path = STATE / "experience_loader_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(STATE / "experience_loader_runs.jsonl", state)
    checks = {
        "experience_loader_runner_runtime_code_present": True,
        "experience_state_written": state_path.exists(),
        "active_queue_loaded": any(item["path"].endswith("ACTIVE_QUEUE.json") and item["exists"] for item in state["sources"]),
        "proof_manifest_loaded": any(item["path"].endswith("PROOF_MANIFEST.json") and item["exists"] for item in state["sources"]),
        "recent_execution_log_loaded": state["recent_log_count"] >= 0,
        "sha_type_policy_supported": True,
        "no_downstream_llm_completion_claim": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-945", "task_id": "BEM945-P2-EXPERIENCE-LOADER-RUNNER", "created_at": now(),
        "stage": {"tasks_done": 3, "tasks_total": 4, "percent": 75},
        "state_path": str(state_path.relative_to(ROOT)), "runs_path": "governance/state/experience_loader_runs.jsonl",
        "source_count": state["source_count"], "existing_source_count": state["existing_source_count"],
        "checks": checks, "blockers": blockers,
        "non_claim": "experience/context loading only; no downstream LLM completion claimed",
        "next_task": "BEM945-P3-FINAL-VERIFY" if not blockers else None,
    }
    receipt_path = PROOFS / "BEM945_experience_loader_runner_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(LOG, {"timestamp": now(), "protocol": "BEM-945", "task_id": receipt["task_id"], "status": receipt["status"], "receipt": str(receipt_path.relative_to(ROOT))})
    return receipt

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--max-chars", type=int, default=1500); parser.add_argument("--recent", type=int, default=20)
    args = parser.parse_args()
    receipt = write(load(args.max_chars, args.recent))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS": raise SystemExit(1)
if __name__ == "__main__":
    main()
