#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
inventory = json.loads((ROOT / "governance/archive/legacy_runtime_inventory.json").read_text(encoding="utf-8"))
items = inventory["items"]
canonical = [i for i in items if i["status"] == "CANONICAL_ACTIVE"]
if not canonical or canonical[0]["workflow"] != ".github/workflows/codex-local.yml":
    raise SystemExit("FAIL: codex-local.yml must be canonical active runtime")
for item in items:
    if item["status"].startswith("ARCHIVED") and item.get("automatic_trigger") not in (False, None):
        raise SystemExit("FAIL: archived runtime has automatic trigger: " + item["workflow"])
print("PASS: BEM-931 RM11 legacy runtime archive inventory")
