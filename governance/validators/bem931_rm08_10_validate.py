#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
policy = json.loads((ROOT / "governance/operator/operator_notification_policy.json").read_text(encoding="utf-8"))
cycle = json.loads((ROOT / "governance/experience/error_rule_cycle.json").read_text(encoding="utf-8"))
return_path = json.loads((ROOT / "governance/return_path/initiator_return_path.json").read_text(encoding="utf-8"))

for forbidden in ["raw technical log", "diff", "stdout", "stderr"]:
    if forbidden not in policy["telegram_canon"]["forbidden_content"]:
        raise SystemExit("FAIL: operator policy missing forbidden content: " + forbidden)

if "rule_registry_new_rule_version" not in cycle["cycle"]:
    raise SystemExit("FAIL: error-to-rule cycle does not update rule version")

routes = {r["initiator"]: r for r in return_path["routes"]}
if not routes["operator"]["result"].startswith("direct"):
    raise SystemExit("FAIL: operator return path must be direct")
for initiator in ["external_auditor_gpt", "external_auditor_claude"]:
    if not routes[initiator]["mailbox"] or not routes[initiator]["wake_up"]:
        raise SystemExit("FAIL: external auditor return path requires mailbox + wake-up")
print("PASS: BEM-931 RM08-RM10 operator report, error cycle, return path")
