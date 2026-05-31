#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

RUNS = Path('governance/state/contour_lifecycle_runs.jsonl')


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '
')


def run_deterministic_cycle(trace_id, contour_id, payload):
    statuses = [
        'input_received',
        'proposal_prepared',
        'proposal_under_audit',
        'proposal_approved',
        'execution_started',
        'execution_result_submitted',
        'result_under_audit',
        'result_approved',
        'contour_result_ready'
    ]
    events = []
    for idx, status in enumerate(statuses):
        events.append({'step': idx+1, 'status': status})
    run = {'trace_id': trace_id, 'created_at': datetime.now(timezone.utc).isoformat(), 'contour_id': contour_id, 'payload': payload, 'events': events, 'status': 'completed', 'proof_ref': 'deterministic_cycle'}
    append_jsonl(RUNS, run)
    return run

if __name__ == '__main__':
    print(json.dumps(run_deterministic_cycle('bem938-selftest','WRK-C1', {'task':'selftest'}), ensure_ascii=False))
