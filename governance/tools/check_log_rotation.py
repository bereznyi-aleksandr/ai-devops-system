# BEM-911 log rotation checker
import json
from pathlib import Path
policy = json.loads(Path("governance/state/log_rotation_policy.json").read_text(encoding="utf-8"))
for target in policy["targets"]:
    p = Path(target)
    size = p.stat().st_size if p.exists() else 0
    print(f"{target}: {size} bytes")
raise SystemExit(0)
