#!/usr/bin/env python3
"""BEM-933 receipt freshness watchdog.

Scans the release gate and critical proof files.  It produces a compact PASS or
BLOCKED receipt so the executor can continue without guessing.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(".")
DEFAULT_RELEASE_GATE = Path("governance/release/bem932_release_gate.json")
DEFAULT_OUT = Path("governance/proofs/BEM933_receipt_watchdog_receipt.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_required(release_gate: Dict[str, Any]) -> List[str]:
    required = [
        "governance/roadmap/ACTIVE_QUEUE.json",
        "governance/proofs/BEM933_active_queue_guard_receipt.json",
        "governance/proofs/BEM932_final_release_verdict_after_live_proofs.md",
        "governance/release/bem932_release_gate.json",
    ]
    for proof in release_gate.get("proofs", {}).values():
        if isinstance(proof, dict) and proof.get("path"):
            required.append(str(proof["path"]))
    return sorted(set(required))


def check_receipts(release_gate_path: Path = DEFAULT_RELEASE_GATE) -> Dict[str, Any]:
    release_gate = load_json(release_gate_path)
    required = collect_required(release_gate)
    missing = [path for path in required if not (ROOT / path).exists()]
    gate_status = release_gate.get("release_status")
    checks = {
        "release_gate_status": gate_status,
        "required_count": len(required),
        "missing_count": len(missing),
    }
    status = "PASS" if gate_status == "PASS" and not missing else "BLOCKED"
    return {
        "status": status,
        "protocol": "BEM-933",
        "receipt_type": "receipt_watchdog",
        "created_at": utc_now(),
        "checks": checks,
        "required": required,
        "missing": missing,
        "next_task": "BEM933-TELEGRAM-DELIVERY-AUDIT" if status == "PASS" else "BEM933-RECEIPT-WATCHDOG-REPAIR",
    }


def write_receipt(path: Path, receipt: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check release/proof receipt freshness")
    parser.add_argument("--release-gate", default=str(DEFAULT_RELEASE_GATE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    receipt = check_receipts(Path(args.release_gate))
    if args.write:
        write_receipt(Path(args.out), receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
