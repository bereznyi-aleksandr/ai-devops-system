#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

PASS = Path('governance/state/object_lifecycle_runs.jsonl')


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '
')


def run_object_task(trace_id, object_id, curator_id, target_contour, payload):
    run = {
        'trace_id': trace_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'object_id': object_id,
        'curator_id': curator_id,
        'target_contour': target_contour,
        'payload': payload,
        'status': 'object_task_accepted',
        'next': 'curator_router.route_to_contour'
    }
    append_jsonl(PASS, run)
    return run

if __name__ == '__main__':
    print(json.dumps(run_object_task('bem938-selftest','OBJ-DIR-001','EL-CUR-DIR-001','DIR-ANALYSIS-CNT', {'task':'selftest'}), ensure_ascii=False))
