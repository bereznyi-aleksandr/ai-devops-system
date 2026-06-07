#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
schema = json.loads((ROOT / "governance/exchange/exchange_registry.schema.json").read_text(encoding="utf-8"))
registry = json.loads((ROOT / "governance/exchange/exchange_registry.json").read_text(encoding="utf-8"))
required = set(schema["required_fields"])
for rec in registry["records"]:
    missing = sorted(required - set(rec))
    if missing:
        raise SystemExit(f"FAIL: exchange record {rec.get('exchange_id')} missing {missing}")
    if rec["managed_channel_id"] == "direct_role_to_role_runtime_channel":
        raise SystemExit("FAIL: direct role-to-role runtime channel is forbidden")
    if not rec["proof_ref"] or not rec["data_version"] or not rec["rule_version"]:
        raise SystemExit("FAIL: proof_ref/data_version/rule_version required")
print("PASS: BEM-931 RM07 horizontal exchange registry")
