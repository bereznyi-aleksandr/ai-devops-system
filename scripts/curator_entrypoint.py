#!/usr/bin/env python3
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import curator_router

LAST_DECISION = ROOT / 'governance/state/curator_last_decision.json'
EXCHANGE = ROOT / 'governance/exchange.jsonl'


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def read_text(path):
    p = Path(path)
    return p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def write_env(name, value):
    env_path = __import__('os').environ.get('GITHUB_ENV')
    if env_path:
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write(f'{name}={value}\n')


def extract_provider_error(text):
    lower = text.lower()
    for marker in ('provider_error:', 'simulate_provider_error:', 'claude_error:', 'cloud_error:'):
        if marker in lower:
            idx = lower.index(marker)
            return text[idx + len(marker):].strip()[:1200]
    needles = ('you have hit your limit', "you've hit your limit", 'resets at', 'http 429', 'rate limit', 'usage limit', 'quota exceeded')
    if any(x in lower for x in needles):
        return text[-1200:]
    return None


def infer_role(text):
    m = re.search(r'ROLE:\s*(analyst|auditor|executor)', text, flags=re.I)
    if m:
        return m.group(1).lower()
    lower = text.lower()
    if 'исполнитель' in lower or 'executor' in lower:
        return 'executor'
    if 'аналитик' in lower or 'analyst' in lower:
        return 'analyst'
    if 'аудитор' in lower or 'auditor' in lower:
        return 'auditor'
    return None


def infer_task(text):
    m = re.search(r'TASK:\s*(.+)', text, flags=re.I | re.S)
    return (m.group(1).strip() if m else text.replace('@curator', 'curator').strip())[:4000]


def main():
    comment_file = sys.argv[1]
    comment = read_text(comment_file)
    trace_id = 'cur_' + uuid.uuid4().hex[:16]
    error_text = extract_provider_error(comment)
    backend, reason = curator_router.route(role='curator', error_text=error_text, success=False)
    if backend == 'gpt_hosted_fallback':
        next_action = 'RUN_HOSTED_GPT_CURATOR'
    elif backend == 'claude':
        next_action = 'ROUTE_TO_CLAUDE_CURATOR'
    elif backend:
        next_action = 'RUN_' + str(backend).upper()
    else:
        next_action = 'DEGRADED_REPORT_ONLY'
    requested_role = infer_role(comment)
    task = infer_task(comment)
    decision = {
        'version': 1,
        'timestamp': now_iso(),
        'trace_id': trace_id,
        'active_backend': backend,
        'routing_reason': reason,
        'next_action': next_action,
        'requested_role': requested_role,
        'task': task,
        'error_detected': bool(error_text)
    }
    LAST_DECISION.parent.mkdir(parents=True, exist_ok=True)
    LAST_DECISION.write_text(json.dumps(decision, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    append_jsonl(EXCHANGE, {'event_id': trace_id, 'timestamp': decision['timestamp'], 'type': 'CURATOR_ROUTING_DECISION', 'source': 'curator_entrypoint', 'backend': backend, 'reason': reason, 'requested_role': requested_role})
    write_env('CURATOR_TRACE_ID', trace_id)
    write_env('ACTIVE_BACKEND', backend or 'none')
    write_env('NEXT_ACTION', next_action)
    write_env('REQUESTED_ROLE', requested_role or 'none')
    write_env('ROUTING_REASON', reason.replace('\n', ' ')[:1000])
    print('BEM-CURATOR-ENTRYPOINT | ROUTING DECISION')
    print('TRACE_ID=' + trace_id)
    print('ACTIVE_BACKEND=' + str(backend or 'none'))
    print('ROUTING_REASON=' + reason.replace('\n', ' ')[:1000])
    print('NEXT_ACTION=' + next_action)
    print('REQUESTED_ROLE=' + str(requested_role or 'none'))
    print('ERROR_DETECTED=' + str(bool(error_text)).lower())
    return 0 if backend else 2


if __name__ == '__main__':
    raise SystemExit(main())
