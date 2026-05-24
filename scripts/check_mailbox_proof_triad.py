#!/usr/bin/env python3
import json
from pathlib import Path
SEP="\n"
def load(path):
    p=Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore")) if p.exists() else {}
    except Exception as exc:
        return {"_load_error":str(exc)}
def read(path):
    p=Path(path)
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
results=list(Path("governance/workflow_dispatch_results").glob("*.status.json")) if Path("governance/workflow_dispatch_results").exists() else []
runtime=load("governance/state/claude_inbound_mailbox_workflow_state.json")
real=[]
mail=Path("governance/audit_mailbox/claude_to_gpt")
if mail.exists():
    for p in sorted(mail.glob("*")):
        if not p.is_file():
            continue
        txt=read(p)
        up=txt.upper()
        low=(p.name+" "+txt).lower()
        bad="NOT CLAUDE APPROVAL" in up or "RUNTIME BLOCKER" in up or "not treat this as claude" in low
        ok=("CLAUDE RESPONSE" in up and "DECISION:" in up and ("APPROVED" in up or "CHANGE_REQUIRED" in up or "BLOCKED" in up))
        if ok and not bad:
            real.append(str(p))
missing=[]
if not results:
    missing.append("workflow_dispatch_results")
if not (runtime.get("started_at") or runtime.get("completed_at")):
    missing.append("claude_runtime_state")
if not real:
    missing.append("real_claude_response")
state={"status":"pass" if not missing else "fail","missing":missing,"dispatch_results_count":len(results),"runtime_started_at":runtime.get("started_at"),"runtime_completed_at":runtime.get("completed_at"),"real_responses":real[-20:]}
Path("governance/state/mailbox_proof_triad_gate_state.json").write_text(json.dumps(state,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps(state,ensure_ascii=False))
raise SystemExit(0 if not missing else 2)
