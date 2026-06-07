#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];out=R/'governance/test_results/bem931_working_contour_negative_latest.json'
p=subprocess.run(['python3',str(R/'governance/runtime/bem931_working_contour.py'),'--fixture','governance/tests/fixtures/operator_objective_invalid_no_objective.json','--output',str(out.relative_to(R)),'--trace-id','BEM931-WORKING-NEGATIVE'],cwd=R,text=True,capture_output=True)
assert p.returncode!=0
r=json.loads(out.read_text(encoding='utf-8'))
assert r.get('ok') is False and 'missing_fields:objective' in r.get('errors',[])
print('PASS: BEM-931 negative fail-closed gate')
