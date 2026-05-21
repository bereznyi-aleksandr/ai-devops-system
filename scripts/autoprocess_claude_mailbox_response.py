#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP='\n'
KYIV=timezone(timedelta(hours=3))
INBOX=[Path('governance/audit_mailbox/claude_to_gpt'),Path('governance/audit_mailbox/external_auditor_to_internal_auditor')]
STATE=Path('governance/state/claude_mailbox_autoprocess_state.json')
HANDOFF=Path('governance/handoff/GPT_NEXT_ACTION.md')
PENDING=Path('governance/tasks/pending/claude_mailbox_autoprocess_next.md')
FINAL=Path('governance/agreements/final')
REPORT=Path('governance/reports/claude_mailbox_autoprocess_report.md')

def load(p):
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding='utf-8', errors='ignore'))
    except Exception: return {}

def decision(text):
    up=text.upper()
    if 'CHANGE_REQUIRED' in up: return 'CHANGE_REQUIRED'
    if 'BLOCKED' in up: return 'BLOCKED'
    if 'APPROVED' in up or 'DECISION: APPROVE' in up: return 'APPROVED'
    return 'MESSAGE'

def scan():
    out=[]
    for d in INBOX:
        if not d.exists(): continue
        for p in sorted(d.glob('*')):
            if not p.is_file(): continue
            txt=p.read_text(encoding='utf-8', errors='ignore')
            low=(p.name+' '+txt).lower()
            if 'bem703' in low or 'bem-703' in low or 'bem712' in low or 'bem-712' in low or 'multi-agent strategy' in low or 'multi-agent system protocol' in low:
                out.append({'path':str(p),'decision':decision(txt),'preview':txt[:1000]})
    return out
now=datetime.now(KYIV).strftime('%Y-%m-%d | %H:%M (UTC+3)')
old=load(STATE); seen=set(old.get('processed_paths',[])); items=scan(); new=[x for x in items if x['path'] not in seen]
status='no_new_response'; latest=None
if new:
    latest=new[-1]; status='processed_'+latest['decision'].lower()
    HANDOFF.parent.mkdir(parents=True, exist_ok=True); PENDING.parent.mkdir(parents=True, exist_ok=True); FINAL.mkdir(parents=True, exist_ok=True)
    if latest['decision']=='APPROVED':
        final=FINAL/'multi_agent_strategy_v2_1_approved_by_claude.md'
        final.write_text('# Multi-Agent Strategy v2.1 | APPROVED BY CLAUDE'+SEP+SEP+'Дата: '+now+SEP+'Source: '+latest['path']+SEP+'Decision: APPROVED'+SEP, encoding='utf-8')
        HANDOFF.write_text('# GPT NEXT ACTION | CLAUDE APPROVED STRATEGY'+SEP+SEP+'Дата: '+now+SEP+'Файл: `'+latest['path']+'`'+SEP+'Final: `'+str(final)+'`'+SEP+'Действие: собрать согласованный протокол v2.1.'+SEP, encoding='utf-8')
        PENDING.write_text('# Pending: finalize approved strategy'+SEP+SEP+'Дата: '+now+SEP+'Source: '+latest['path']+SEP, encoding='utf-8')
    elif latest['decision']=='CHANGE_REQUIRED':
        HANDOFF.write_text('# GPT NEXT ACTION | CLAUDE CHANGE REQUIRED'+SEP+SEP+'Дата: '+now+SEP+'Файл: `'+latest['path']+'`'+SEP+'Действие: внести правки и отправить следующий раунд.'+SEP, encoding='utf-8')
        PENDING.write_text('# Pending: apply Claude changes'+SEP+SEP+'Дата: '+now+SEP+'Source: '+latest['path']+SEP, encoding='utf-8')
    elif latest['decision']=='BLOCKED':
        HANDOFF.write_text('# GPT NEXT ACTION | CLAUDE BLOCKED'+SEP+SEP+'Дата: '+now+SEP+'Файл: `'+latest['path']+'`'+SEP+'Действие: подготовить unblock plan.'+SEP, encoding='utf-8')
        PENDING.write_text('# Pending: resolve Claude blocker'+SEP+SEP+'Дата: '+now+SEP+'Source: '+latest['path']+SEP, encoding='utf-8')
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps({'schema_version':'claude_mailbox_autoprocess_state.v1','status':status,'checked_at':now,'items':items,'new_items':new,'processed_paths':sorted(set(list(seen)+[x['path'] for x in new])),'operator_role':'none','latest':latest},indent=2,ensure_ascii=False)+SEP, encoding='utf-8')
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text('# Claude Mailbox Autoprocess Report'+SEP+SEP+'Дата: '+now+SEP+'Status: '+status+SEP+'New items: '+str(len(new))+SEP+'Operator role: none'+SEP, encoding='utf-8')
print(json.dumps({'status':status,'new_items':len(new),'operator_role':'none'},ensure_ascii=False))
