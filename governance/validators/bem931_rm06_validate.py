#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
data = json.loads((ROOT / "governance/links/vertical_links.json").read_text(encoding="utf-8"))
assert data["inheritance"], "missing inheritance"
assert data["escalation"], "missing escalation"
assert "direct_role_to_role_between_objects" in data["forbidden"]
for item in data["inheritance"]:
    if item.get("rule_scope") in ("system", "director"):
        assert item.get("rule_version_required") is True
print("PASS: BEM-931 RM06 vertical links")
