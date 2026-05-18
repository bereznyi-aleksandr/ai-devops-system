#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATE_PATH = Path("governance/state/curator_hourly_report_state.json")
STATUS_PATH = Path("governance/tmp/curator_hourly_report_delivery.txt")
REPORT_PATH = Path("governance/reports/curator_hourly_report_runtime.md")
def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
state = load_json(STATE_PATH)
status = STATUS_PATH.read_text(encoding="utf-8", errors="ignore").strip() if STATUS_PATH.exists() else "unknown"
state["telegram_delivery"] = status
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
blocker = state.get("blocker")
REPORT_PATH.write_text("# Curator Hourly Report Runtime" + SEP + SEP + "Telegram delivery: " + status + SEP + "Selected provider: " + str(state.get("selected_provider", "unknown")) + SEP + "Reserve used: " + str(state.get("reserve_used", "unknown")) + SEP + "Blocker: " + ("null" if blocker is None else json.dumps(blocker, ensure_ascii=False)) + SEP, encoding="utf-8")
print(json.dumps({"telegram_delivery": status, "blocker": blocker}, ensure_ascii=False))
