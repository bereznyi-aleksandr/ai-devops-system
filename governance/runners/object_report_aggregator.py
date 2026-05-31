#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

ROLE_REPORTS = Path('governance/state/role_reports.jsonl')
OBJECT_REPORTS = Path('governance/state/object_reports.jsonl')


def aggregate(trace_id, object_id):
    reports = []
    if ROLE_REPORTS.exists():
        for line in ROLE_REPORTS.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.strip():
                obj = json.loads(line)
                if obj.get('trace_id') == trace_id:
                    reports.append(obj)
    result = {'trace_id': trace_id, 'created_at': datetime.now(timezone.utc).isoformat(), 'object_id': object_id, 'role_reports_count': len(reports), 'status': 'aggregated', 'reports': reports}
    OBJECT_REPORTS.parent.mkdir(parents=True, exist_ok=True)
    with OBJECT_REPORTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '
')
    return result

if __name__ == '__main__':
    print(json.dumps(aggregate('bem938-selftest','OBJ-WRK-001'), ensure_ascii=False))
