# BEM-893 end-to-end dispatch selftest runner
import json
from pathlib import Path
report = json.loads(Path("governance/reports/BEM893_E2E_DISPATCH_SELFTEST.json").read_text(encoding="utf-8"))
print(report["status"])
for check in report["checks"]:
    print(("PASS" if check["ok"] else "FAIL") + " | " + check["name"] + " | " + check["detail"])
raise SystemExit(0 if report["status"] == "PASS" else 1)
