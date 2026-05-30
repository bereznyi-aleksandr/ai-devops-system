# BEM-904 pilot evaluation dashboard validator
import json
from pathlib import Path
dashboard = json.loads(Path("governance/pilot/evaluation/pilot_dashboard.json").read_text(encoding="utf-8"))
errors = []
for key, ok in dashboard.get("readiness", {}).items():
    if not ok:
        errors.append(key + " not ready")
profile = json.loads(Path(dashboard["evaluation_profile"]).read_text(encoding="utf-8"))
sla = json.loads(Path(dashboard["sla_template"]).read_text(encoding="utf-8"))
if len(profile.get("metrics", [])) < 6:
    errors.append("metrics insufficient")
if len(sla.get("service_levels", [])) < 4:
    errors.append("sla insufficient")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
