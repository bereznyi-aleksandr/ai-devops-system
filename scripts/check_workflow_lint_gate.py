#!/usr/bin/env python3
from pathlib import Path
import json
import sys

WORKFLOWS = Path('.github/workflows')
violations=[]
for path in sorted(list(WORKFLOWS.glob('*.yml')) + list(WORKFLOWS.glob('*.yaml'))):
    text=path.read_text(encoding='utf-8', errors='ignore')
    lines=text.splitlines()
    # Rule 1: do not embed python heredoc inside workflow YAML.
    for i,line in enumerate(lines,1):
        low=line.lower()
        if 'python3 - <<' in low or 'python - <<' in low or 'cat <<' in low and '.py' in low:
            violations.append({'file':str(path),'line':i,'rule':'NO_INLINE_HEREDOC_CODE','text':line.strip()})
    # Rule 2: long run blocks are suspicious and must move to scripts/*.py.
    in_run=False; run_indent=None; block_len=0; start=0
    for i,line in enumerate(lines,1):
        stripped=line.lstrip(' ')
        indent=len(line)-len(stripped)
        if stripped.startswith('run: |') or stripped.startswith('run: >'):
            in_run=True; run_indent=indent; block_len=0; start=i
            continue
        if in_run:
            if stripped and indent<=run_indent:
                if block_len>8:
                    violations.append({'file':str(path),'line':start,'rule':'LONG_RUN_BLOCK_MOVE_TO_SCRIPT','length':block_len})
                in_run=False; run_indent=None; block_len=0
            else:
                if stripped and not stripped.startswith('#'):
                    block_len+=1
    if in_run and block_len>8:
        violations.append({'file':str(path),'line':start,'rule':'LONG_RUN_BLOCK_MOVE_TO_SCRIPT','length':block_len})

result={'schema_version':'workflow_lint_gate_result.v1','status':'pass' if not violations else 'failed','violations':violations}
Path('governance/reports').mkdir(parents=True,exist_ok=True)
Path('governance/reports/workflow_lint_gate_result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
if violations:
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(1)
print(json.dumps(result,ensure_ascii=False))
