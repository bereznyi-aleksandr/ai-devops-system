#!/usr/bin/env python3
from pathlib import Path
required = [
  'governance/runners/object_lifecycle_runner.py',
  'governance/runners/curator_router.py',
  'governance/runners/contour_lifecycle_runner.py',
  'governance/runners/role_report_writer.py',
  'governance/runners/object_report_aggregator.py',
  'governance/runners/testing_contour_assignment.py'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
print('BEM-938 Block G runners validator PASS')
