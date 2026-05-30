# BEM-890 dispatch contour validator
import json
from pathlib import Path
queue = Path("governance/dispatch/dispatch_queue.jsonl")
messages = Path("governance/messages/managed_channel_messages.jsonl")
errors = []
if not queue.exists():
    errors.append("dispatch queue missing")
if not messages.exists():
    errors.append("message log missing")
items = [] if not queue.exists() else [json.loads(x) for x in queue.read_text(encoding="utf-8").splitlines() if x.strip()]
msg_text = "" if not messages.exists() else messages.read_text(encoding="utf-8")
for item in items:
    if item.get("target_contour") not in ["WRK-C1","WRK-C2","WRK-C3"]:
        errors.append(f"{item.get('dispatch_id')}: invalid contour")
    if "MSG-" + item.get("dispatch_id", "") not in msg_text:
        errors.append(f"{item.get('dispatch_id')}: message missing")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
