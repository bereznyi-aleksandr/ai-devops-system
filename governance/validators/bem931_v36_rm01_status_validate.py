#!/usr/bin/env python3
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
status = json.loads((ROOT / "governance/status/bem931_v36_working_contour_status.json").read_text(encoding="utf-8"))
lock = json.loads((ROOT / "governance/release/bem931_v36_release_lock.json").read_text(encoding="utf-8"))
gap = ROOT / "governance/reports/bem931_v36_gap_report.md"
assert status["system_status"] == "WORKING_CONTOUR_NOT_READY"
assert status["release_status"] == "BLOCKED"
assert lock["release_status"] == "BLOCKED"
assert "RM-17" in lock["required_pass"]
assert gap.exists() and "WORKING_CONTOUR_NOT_READY" in gap.read_text(encoding="utf-8")
print("PASS: BEM-931 v3.6 RM-01 status reset")
