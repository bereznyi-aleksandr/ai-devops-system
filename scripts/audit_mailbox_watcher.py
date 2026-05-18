#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP='\n'
KYIV=timezone(timedelta(hours=3))
INBOUND=[Path('governance/audit_mailbox/claude_to_gpt'),Path('governance/audit_mailbox/external_auditor_to_internal_auditor')]
STATE=Path('governance/state/audit_mailbox_watcher_state.json')
REPORT=Path('governance/reports/audit_mailbox_watcher_report.md')
OUT=Path('governance/telegram/outbox/audit_mailbox_notification.json')
ACTIVE=Path('governance/agreements/active')
def load(p):
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding='utf-8',errors='ignore'))
    except Exception: return {}
def decision(text):
    up=text.upper()
    if 'DECISION: APPROVE' in up or 'APPROVE' in up: return 'APPROVE'
    if 'CHANGE_REQUIRED' in up: return 'CHANGE_REQUIRED'
    if 'BLOCKED' in up: return 'BLOCKED'
    return 'MESSAGE'
def subject(text,path):
    for line in text.splitlines():
        s=line.strip('# ').strip()
        if s: return s[:140]
    return Path(path).name
now=datetime.now(KYIV).strftime('%Y-%m-%d | %H:%M (UTC+3)')
old=load(STATE); seen=set(old.get('seen_files',[])); items=[]
for d in INBOUND:
    if d.exists():
        for f in sorted(d.glob('*')):
            if f.is_file():
                t=f.read_text(encoding='utf-8',errors='ignore')
                items.append({'path':str(f),'size':f.stat().st_size,'decision':decision(t),'subject':subject(t,str(f))})
new=[x for x in items if x['path'] not in seen]
active=[]
if ACTIVE.exists():
    for f in sorted(ACTIVE.glob('*.json')):
        data=load(f); active.append({'path':str(f),'status':data.get('status'),'next_action':data.get('next_action')})
status='new_mail' if new else 'no_new_mail'
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps({'schema_version':'audit_mailbox_watcher_state.v1','status':status,'checked_at':now,'seen_files':[x['path'] for x in items],'new_items':new,'all_items':items,'active_agreements':active,'blocker':None},indent=2,ensure_ascii=False)+SEP,encoding='utf-8')
lines=['# Audit Mailbox Watcher','', 'Дата: '+now, '', 'Status: '+status, '', '## New items']
lines += [('- '+x['decision']+' | '+x['path']+' | '+x['subject']) for x in new] or ['none']
lines += ['', '## Active agreements']
lines += [('- '+str(x.get('status'))+' | '+x['path']+' | next: '+str(x.get('next_action'))) for x in active] or ['none']
REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(SEP.join(lines)+SEP,encoding='utf-8')
if new:
    OUT.parent.mkdir(parents=True,exist_ok=True)
    msg='BEM-MAILBOX | Ответ Claude получен\nДата: '+now+'\nНовых сообщений: '+str(len(new))+'\nРешение: '+new[-1]['decision']+'\nФайл: '+new[-1]['path']
    OUT.write_text(json.dumps({'schema_version':'telegram_operator_notification.v1','type':'audit_mailbox_new_response','status':'pending_delivery','created_at':now,'message':msg,'items':new},indent=2,ensure_ascii=False)+SEP,encoding='utf-8')
print(json.dumps({'status':status,'new_items':len(new)},ensure_ascii=False))
