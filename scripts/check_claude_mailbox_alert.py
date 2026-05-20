#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SEP="\n"
KYIV=timezone(timedelta(hours=3))
OUT=Path("governance/tmp/claude_mailbox_alert_message.txt")
STATE=Path("governance/state/claude_mailbox_monitor_state.json")
ACTIVE_DIR=Path("governance/agreements/active")
MAILBOX_DIRS=[Path("governance/audit_mailbox/claude_to_gpt"), Path("governance/audit_mailbox/external_auditor_to_internal_auditor")]

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def active_agreements():
    items=[]
    if ACTIVE_DIR.exists():
        for p in sorted(ACTIVE_DIR.glob("*.json")):
            data=load_json(p)
            if data:
                items.append({"path":str(p),"agreement_id":data.get("agreement_id"),"status":data.get("status"),"next_action":data.get("next_action")})
    return items

def scan_mailbox():
    hits=[]
    for d in MAILBOX_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*")):
            if not p.is_file():
                continue
            txt=p.read_text(encoding="utf-8", errors="ignore")
            upper=txt.upper()
            if "BEM-703" in txt or "MULTI-AGENT STRATEGY" in upper or "APPROVED" in upper or "CHANGE_REQUIRED" in upper or "BLOCKED" in upper:
                decision="UNKNOWN"
                if "APPROVED" in upper:
                    decision="APPROVED"
                if "CHANGE_REQUIRED" in upper:
                    decision="CHANGE_REQUIRED"
                if "BLOCKED" in upper:
                    decision="BLOCKED"
                hits.append({"path":str(p),"decision":decision,"mtime":p.stat().st_mtime})
    return hits

now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
prev=load_json(STATE)
hits=scan_mailbox()
active=active_agreements()
known=set(prev.get("notified_paths",[]))
new_hits=[h for h in hits if h["path"] not in known]
status="no_new_claude_response"
message=""
if new_hits:
    status="new_claude_response_detected"
    message="BEM-703 | CLAUDE RESPONSE DETECTED\nДата: "+now+"\n\nНайден новый ответ Claude в mailbox. Открой GPT, чтобы он прочитал и зафиксировал согласованный протокол.\n\n"+"\n".join(["- "+h["decision"]+" | "+h["path"] for h in new_hits])+"\n"
else:
    message=""
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps({"schema_version":"claude_mailbox_monitor_state.v1","status":status,"checked_at":now,"active_agreements":active,"hits":hits,"notified_paths":sorted(set(list(known)+[h["path"] for h in new_hits]))},indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(message,encoding="utf-8")
print(json.dumps({"status":status,"new_hits":len(new_hits)},ensure_ascii=False))
