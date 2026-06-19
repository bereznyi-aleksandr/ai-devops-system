#!/usr/bin/env python3
"""Proof manifest updater runtime for BEM-943.

Scans governance/proofs/*.json, builds governance/proofs/PROOF_MANIFEST.json, and writes
an auditable receipt. This is evidence indexing only; it does not claim downstream LLM completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
MANIFEST = PROOFS / "PROOF_MANIFEST.json"
EXECUTION_LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"_non_object_json": True, "value_type": type(value).__name__}
    except Exception as exc:
        return {"_invalid_json": True, "error": str(exc)}


def scan(limit: int | None = None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in sorted(PROOFS.glob("*.json")):
        if path.name == "PROOF_MANIFEST.json":
            continue
        raw = path.read_bytes()
        doc = read_json(path)
        entries.append({
            "path": str(path.relative_to(ROOT)),
            "name": path.name,
            "size": len(raw),
            "sha256": sha256_bytes(raw),
            "status": doc.get("status"),
            "protocol": doc.get("protocol"),
            "task_id": doc.get("task_id"),
            "blockers": doc.get("blockers"),
            "created_at": doc.get("created_at") or doc.get("verified_at") or doc.get("timestamp"),
            "invalid_json": bool(doc.get("_invalid_json")),
        })
    if limit is not None:
        entries = entries[-limit:]
    by_protocol: dict[str, int] = {}
    invalid_json = 0
    blocked = 0
    for entry in entries:
        protocol = entry.get("protocol") or "UNKNOWN"
        by_protocol[protocol] = by_protocol.get(protocol, 0) + 1
        invalid_json += 1 if entry.get("invalid_json") else 0
        blocked += 1 if entry.get("status") == "BLOCKED" else 0
    return {
        "status": "PASS" if invalid_json == 0 else "BLOCKED",
        "protocol": "BEM-943",
        "task_id": "BEM943-P2-PROOF-MANIFEST-UPDATER",
        "created_at": now(),
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "entry_count": len(entries),
        "by_protocol": by_protocol,
        "invalid_json_count": invalid_json,
        "blocked_receipt_count": blocked,
        "entries": entries,
        "non_claim": "proof manifest indexing only; no downstream LLM completion claimed",
    }


def write_manifest(manifest: dict[str, Any]) -> None:
    PROOFS.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_log(receipt: dict[str, Any]) -> None:
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": now(),
            "protocol": "BEM-943",
            "task_id": receipt["task_id"],
            "status": receipt["status"],
            "receipt": "governance/proofs/BEM943_proof_manifest_updater_receipt.json",
            "manifest": str(MANIFEST.relative_to(ROOT)),
        }, ensure_ascii=False, sort_keys=True) + "\n")


def build_receipt(manifest: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "proof_manifest_updater_runtime_code_present": True,
        "manifest_written": MANIFEST.exists(),
        "manifest_has_entries": manifest.get("entry_count", 0) > 0,
        "invalid_json_absent": manifest.get("invalid_json_count", 0) == 0,
        "non_claim_present": "downstream LLM" in manifest.get("non_claim", ""),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-943",
        "task_id": "BEM943-P2-PROOF-MANIFEST-UPDATER",
        "created_at": now(),
        "stage": {"tasks_done": 3, "tasks_total": 4, "percent": 75},
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "entry_count": manifest.get("entry_count"),
        "checks": checks,
        "blockers": blockers,
        "non_claim": "proof manifest indexing only; no downstream LLM completion claimed",
        "next_task": "BEM943-P3-FINAL-VERIFY" if not blockers else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = scan(args.limit)
    write_manifest(manifest)
    receipt = build_receipt(manifest)
    receipt_path = PROOFS / "BEM943_proof_manifest_updater_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_log(receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
