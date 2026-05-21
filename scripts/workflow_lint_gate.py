#!/usr/bin/env python3
import json
from pathlib import Path
SEP="\n"
ROOT=Path(".github/workflows")
BASELINE=Path("governance/workflow_lint/baseline.json")
REPORT=Path("governance/reports/workflow_lint_report.md")
STATE=Path("governance/state/workflow_lint_gate_state.json")

def scan():
    violations=[]
    if not ROOT.exists():
        return violations
    for p in sorted(list(ROOT.glob("*.yml"))+list(ROOT.glob("*.yaml"))):
        lines=p.read_text(errors="ignore").splitlines()
        for i,line in enumerate(lines, start=1):
            text=line.strip()
            if "python3 - <<" in text or "python - <<" in text:
                violations.append({"file":str(p),"line":i,"rule":"NO_INLINE_CODE","text":text[:120]})
            if "<<" in text and ("PY" in text or "EOF" in text or "MSG" in text):
                violations.append({"file":str(p),"line":i,"rule":"NO_INLINE_HEREDOC","text":text[:120]})
        in_run=False; start=0; count=0
        for i,line in enumerate(lines, start=1):
            stripped=line.strip()
            if stripped=="run: |":
                if in_run and count>8:
                    violations.append({"file":str(p),"line":start,"rule":"LONG_RUN_BLOCK_MOVE_TO_SCRIPT","length":count})
                in_run=True; start=i; count=0
                continue
            if in_run:
                if line.startswith("      ") or line.startswith("        ") or line.strip()=="":
                    count+=1
                else:
                    if count>8:
                        violations.append({"file":str(p),"line":start,"rule":"LONG_RUN_BLOCK_MOVE_TO_SCRIPT","length":count})
                    in_run=False; count=0
        if in_run and count>8:
            violations.append({"file":str(p),"line":start,"rule":"LONG_RUN_BLOCK_MOVE_TO_SCRIPT","length":count})
    return violations

def key(v):
    return v.get("file","")+"|"+v.get("rule","")+"|"+str(v.get("line",0))+"|"+v.get("text","")

violations=scan()
if BASELINE.exists():
    try:
        base=json.loads(BASELINE.read_text(errors="ignore"))
    except:
        base={}
else:
    base={}
base_keys=set(base.get("violation_keys",[]))
current_keys=[key(v) for v in violations]
new=[v for v in violations if key(v) not in base_keys]
resolved=[k for k in base_keys if k not in set(current_keys)]
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps({"schema_version":"workflow_lint_gate_state.v1","status":"failed_new_violations" if new else "passed_with_baseline","violation_count":len(violations),"new_violation_count":len(new),"resolved_baseline_count":len(resolved),"new_violations":new,"resolved_baseline_keys":resolved},indent=2,ensure_ascii=False)+SEP)
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Workflow Lint Gate Report"+SEP+SEP+"Status: "+("FAILED_NEW_VIOLATIONS" if new else "PASSED_WITH_BASELINE")+SEP+"Total violations: "+str(len(violations))+SEP+"New violations: "+str(len(new))+SEP+"Resolved baseline: "+str(len(resolved))+SEP)
if new:
    raise SystemExit(1)
print(json.dumps({"status":"passed_with_baseline","violation_count":len(violations),"new_violation_count":0},ensure_ascii=False))
