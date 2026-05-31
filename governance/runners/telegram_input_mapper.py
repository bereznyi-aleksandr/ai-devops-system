#!/usr/bin/env python3
from datetime import datetime, timezone
import json

DEFAULT_TARGET = 'EL-CUR-GD-001'


def classify_command(text):
    t = (text or '').strip().lower()
    if t.startswith('/status'):
        return 'status'
    if t.startswith('/report'):
        return 'report'
    if t.startswith('/approve'):
        return 'approve'
    if t.startswith('/reject'):
        return 'reject'
    if t.startswith('/gate'):
        return 'gate'
    if t.startswith('/help'):
        return 'help'
    return 'task'


def map_payload(payload, trace_id):
    message = payload.get('message', {}) if isinstance(payload, dict) else {}
    chat = message.get('chat', {})
    user = message.get('from', {})
    text = message.get('text', '')
    return {
        'trace_id': trace_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_channel': 'Telegram',
        'operator_id': str(user.get('id', 'unknown')),
        'chat_id': str(chat.get('id', 'unknown')),
        'command': classify_command(text),
        'payload': {'text': text},
        'target_curator': DEFAULT_TARGET,
        'policy_decision': 'allow',
        'receipt_status': 'queued'
    }

if __name__ == '__main__':
    sample = {'message': {'chat': {'id': 1}, 'from': {'id': 2}, 'text': '/status'}}
    print(json.dumps(map_payload(sample, 'telegram-mapper-selftest'), ensure_ascii=False))
