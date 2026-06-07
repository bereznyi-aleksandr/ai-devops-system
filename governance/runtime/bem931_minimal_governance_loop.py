#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    "governance/registry/objects_registry.json",
    "governance/registry/elements_registry.json",
    "governance/registry/rule_registry.json",
    "governance/registry/element_prompt_profiles.json",
    "governance/links/vertical_links.json",
    "governance/exchange/exchange_registry.json",
    "governance/operator/operator_notification_policy.json",
    "governance/experience/error_rule_cycle.json",
    "governance/return_path/initiator_return_path.json",
    "governance/archive/legacy_runtime_inventory.json",
]

def main() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        raise SystemExit("FAIL: missing prerequisites: " + ", ".join(missing))
    for rel in REQUIRED:
        json.loads((ROOT / rel).read_text(encoding="utf-8"))
    print("PASS: Minimal Governance Loop prerequisites")
    print("FLOW: curator -> analyst -> auditor -> executor -> auditor -> curator")
    print("GATE: no direct role-to-role runtime channel; horizontal exchange is curator-mediated")

if __name__ == "__main__":
    main()
