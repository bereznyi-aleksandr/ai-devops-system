#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

REPORTS = Path('governance/state/role_reports.jsonl')


def write_role_report(trace_id, contour_id, role, provider_id, status, summary, proof_ref):
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'trace_id': trace_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'contour_id': contour_id,
        'role': role,
        'provider_id': provider_id,
        'status': status,
        'summary': summary,
        'proof_ref': proof_ref
    }
    with REPORTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False) + '
')
    return report

if __name__ == '__main__':
    print(json.dumps(write_role_report('bem938-selftest','WRK-C1','auditor','CLAUDE-AUDITOR','PASS','selftest report','stdout'), ensure_ascii=False))
