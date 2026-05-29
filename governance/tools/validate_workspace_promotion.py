# BEM-886 workspace promotion validator
import json
from pathlib import Path
policy = json.loads(Path("governance/state/workspace_promotion_policy.json").read_text(encoding="utf-8"))
log = Path(policy["log"])
errors = []
for line in log.read_text(encoding="utf-8").splitlines():
    rec = json.loads(line)
    req = policy["required_for_main"] if rec.get("target_workspace") == "main" else policy["required_for_testing"]
    for field in req:
        if field not in rec:
            errors.append(f"{rec.get('artifact_id','unknown')}: missing {field}")
    if rec.get("target_workspace") == "main" and not Path(rec.get("proof", "")).exists():
        errors.append(f"{rec.get('artifact_id','unknown')}: proof missing")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
