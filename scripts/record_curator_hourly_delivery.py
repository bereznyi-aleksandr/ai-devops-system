#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATE = Path("governance/state/curator_hourly_report_state.json")
DELIVERY = Path("governance/tmp/curator_hourly_report_delivery.txt")
RESPONSE = Path("governance/tmp/curator_hourly_report_response.json")
REPORT = Path("governance/reports/curator_hourly_report_delivery.md")
def load_state():
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8", errors="ignore"))
    except:
        return {}
def read(path, default="missing"):
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else default
delivery = read(DELIVERY)
state = load_state()
state["telegram_delivery"] = delivery
state["status"] = "sent" if delivery == "sent" else "not_sent"
state["blocker"] = None if delivery == "sent" else {"code":"TELEGRAM_HOURLY_NOT_SENT", "delivery": delivery}
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Curator Hourly Delivery" + SEP + SEP + "Telegram delivery: " + delivery + SEP, encoding="utf-8")
print(json.dumps({"telegram_delivery": delivery, "status": state["status"]}, ensure_ascii=False))
