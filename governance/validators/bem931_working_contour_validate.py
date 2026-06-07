#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];out=R/'governance/test_results/bem931_working_contour_latest.json'
subprocess.check_call(['python3',str(R/'governance/runtime/bem931_working_contour.py'),'--fixture','governance/tests/fixtures/operator_objective_valid.json','--output',str(out.relative_to(R)),'--trace-id','BEM931-WORKING-ACCEPTANCE'],cwd=R)
r=json.loads(out.read_text(encoding='utf-8'))
need={'GD.CURATOR','DIR.CURATOR','WRK.ANALYST','WRK.AUDITOR','WRK.EXECUTOR'}
assert r.get('ok') is True and r.get('repo_level_pass') is True and r.get('release_pass') is False
assert need.issubset(set(r.get('actors',[])))
for p in [r['operator_report_path'],r['receipt_path'],r['execution']['artifact_relpath']]: assert (R/p).exists(),p
assert r['audit']['precheck']['ok'] is True and r['audit']['postcheck']['ok'] is True
assert 'EXP.BEM931.NO_STATUS_ONLY' in r['experience']['applied_experience_ids']
print('PASS: BEM-931 working governance contour')
