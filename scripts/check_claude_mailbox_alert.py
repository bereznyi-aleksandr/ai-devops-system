#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/claude_mailbox_monitor_state.json")
HANDOFF=Path("governance/handoff/GPT_NEXT_ACTION.md")
PENDING=Path("governance/tasks/pending/claude_mailbox_autoprocess_next.md")
ACTIVE_DIR=Path("governance/agreements/active")
FINAL_DIR=Path("governance/agreements/final")
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
                decision="MESSAGE"
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
known=set(prev.get("processed_paths",[]))
new_hits=[h for h in hits if h["path"] not in known]
status="no_new_claude_response"
if new_hits:
    status="new_claude_response_ready_for_gpt_processing"
    latest=new_hits[-1]
    HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    HANDOFF.write_text("# GPT NEXT ACTION | CLAUDE MAILBOX RESPONSE READY"+SEP+SEP+"Дата: "+now+SEP+SEP+"Оператор не участвует в обработке. GPT должен прочитать ответ Claude из repo/mailbox и довести согласование до результата."+SEP+SEP+"Файл: `"+latest["path"]+"`"+SEP+"Decision detected: "+latest["decision"]+SEP+SEP+"Действие: создать Codex task для фиксации результата, обновить active agreement, сформировать согласованный протокол или changes request."+SEP, encoding="utf-8")
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    PENDING.write_text("# Claude mailbox autoprocess pending"+SEP+SEP+"Дата: "+now+SEP+"Файл: "+latest["path"]+SEP+"Decision: "+latest["decision"]+SEP+"Operator relay is forbidden. GPT/Codex must process repo artifact directly."+SEP, encoding="utf-8")
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps({"schema_version":"claude_mailbox_autoprocess_state.v2_no_operator","status":status,"checked_at":now,"active_agreements":active,"hits":hits,"new_hits":new_hits,"processed_paths":sorted(set(list(known)+[h["path"] for h in new_hits])),"operator_notification":"disabled","operator_role":"none_in_routine_agreement_processing"},indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps({"status":status,"new_hits":len(new_hits),"operator_notification":"disabled"},ensure_ascii=False))
