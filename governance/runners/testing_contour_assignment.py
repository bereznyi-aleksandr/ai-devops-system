#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

ASSIGNMENTS = Path('governance/state/testing_contour_assignments.jsonl')
ALLOWED = {'WRK-C1','WRK-C2','WRK-C3'}


def assign_testing_contour(trace_id, contour_id, reason):
    if contour_id not in ALLOWED:
        return {'status': 'rejected', 'reason': 'contour_not_testing_capable'}
    assignment = {'trace_id': trace_id, 'created_at': datetime.now(timezone.utc).isoformat(), 'contour_id': contour_id, 'mode': 'temporary_testing', 'reason': reason, 'status': 'assigned'}
    ASSIGNMENTS.parent.mkdir(parents=True, exist_ok=True)
    with ASSIGNMENTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(assignment, ensure_ascii=False) + '
')
    return assignment

if __name__ == '__main__':
    print(json.dumps(assign_testing_contour('bem938-selftest','WRK-C3','selftest'), ensure_ascii=False))
