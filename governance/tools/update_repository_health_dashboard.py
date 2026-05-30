# BEM-898 repository health dashboard updater
import json
from pathlib import Path
dashboard = json.loads(Path("governance/dashboard/repository_health.json").read_text(encoding="utf-8"))
print(dashboard["status"])
for check in dashboard["checks"]:
    print(("PASS" if check["ok"] else "FAIL") + " | " + check["id"])
raise SystemExit(0 if dashboard["status"] == "HEALTHY" else 1)
