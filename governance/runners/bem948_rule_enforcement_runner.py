#!/usr/bin/env python3
"""BEM-948 P2 runtime enforcers: RULE-011 evidence; RULE-012 continuity."""
import argparse, hashlib, importlib.util, json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
QDEF=ROOT/"governance/roadmap/ACTIVE_QUEUE.json"
R="governance/runners/bem948_rule_enforcement_runner.py"
G="governance/runners/active_queue_guard.py"
IDS=[f"RULE-{n:03d}" for n in range(4,13)]

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):
    x=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(x,dict): raise ValueError("json_object_required")
    return x
def w(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2)+"\n",encoding="utf-8")
def shae(x,p="$"):
    z=[]
    if isinstance(x,dict):
        for k,v in x.items():
            if (k=="sha" or k.endswith("_sha")) and isinstance(v,str) and v and k+"_type" not in x and "sha_type" not in x:z+=[p+"."+k+":sha_type_missing"]
            z+=shae(v,p+"."+k)
    if isinstance(x,list):
        for i,v in enumerate(x):z+=shae(v,p+f"[{i}]")
    return z
def evid(x):
    z=shae(x); rt=x.get("runtime_execution_claim") is True or x.get("evidence_kind")=="runtime_execution"
    ex=x.get("execution"); done=isinstance(ex,dict) and any(ex.get(k) for k in ("executed_at","completed_at","run_id"))
    if x.get("status")=="PASS" and rt and not done and not isinstance(x.get("terminal_report"),dict):z+=["runtime_pass_without_executed_or_terminal_evidence"]
    return z
def loc(q):
    t=q.get("tasks"); z=[]
    if not isinstance(t,list):return ["tasks_list_missing"]
    r=[a for a in t if isinstance(a,dict) and a.get("status") in ("IN_PROGRESS","PENDING")]
    c=q.get("current_task"); ids={str(a.get("id")) for a in t if isinstance(a,dict) and a.get("id")}
    if r:
        if not c:z+=["current_task_missing_with_runnable_task"]
        elif str(c) not in ids:z+=["current_task_not_in_tasks"]
        elif not any(str(a.get("id"))==str(c) for a in r):z+=["current_task_not_runnable"]
        if q.get("queue_state") not in ("ACTIVE","IN_PROGRESS"):z+=["queue_state_not_active_with_runnable_task"]
    elif c:z+=["current_task_set_without_runnable_task"]
    return z
def leg(root,q):
    try:
        s=importlib.util.spec_from_file_location("aqg",root/G)
        if not s or not s.loader:raise RuntimeError("load")
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);o=m.validate(q)
        return ([] if isinstance(o,dict) and o.get("status")=="PASS" else ["legacy_guard_rejected_queue"],o)
    except Exception as e:return ([f"legacy_guard_error:{type(e).__name__}"],{"status":"BLOCKED"})
def tests(root):
    e=evid({"status":"PASS","runtime_execution_claim":True,"artifact_sha":"x"})
    l=loc({"queue_state":"ACTIVE","current_task":"X","tasks":[{"id":"Y","status":"PENDING"}]})
    g,_=leg(root,{"queue_state":"ACTIVE","current_task":"X","tasks":[{"id":"Y","status":"PENDING"}]})
    return {"r11_sha_type":any(x.endswith("artifact_sha:sha_type_missing") for x in e),"r11_runtime": "runtime_pass_without_executed_or_terminal_evidence" in e,"r12_local":"current_task_not_in_tasks" in l,"r12_legacy":bool(g)}
def make(root,qp,q):
    a=loc(q);b,o=leg(root,q);t=tests(root);bad=a+b+[k for k,v in t.items() if not v]
    rows={i:{"enforcement_status":"NOT_VERIFIED","enforcement_paths":[]} for i in IDS}
    rows["RULE-011"]={"enforcement_status":"ENFORCED","enforcement_paths":[R],"runtime_checks":{"sha_type_rejected":t["r11_sha_type"],"runtime_pass_rejected":t["r11_runtime"]}}
    rows["RULE-012"]={"enforcement_status":"ENFORCED","enforcement_paths":[R,G],"runtime_checks":{"local_invalid_rejected":t["r12_local"],"legacy_invalid_rejected":t["r12_legacy"],"current_local_valid":not a,"current_legacy_valid":not b},"legacy_guard_result":o}
    x={"schema_version":1,"protocol":"BEM-948","task_id":"BEM948-P2-RULE-ENFORCEMENT-VERIFICATION","created_at":now(),"status":"PASS" if not bad else "BLOCKED","evidence_kind":"runtime_execution","runtime_execution_claim":True,"execution":{"executed_at":now(),"runner_path":R,"runner_sha":h(root/R),"runner_sha_type":"sha256_content","github_run_id":os.getenv("GITHUB_RUN_ID","")},"queue_input":{"path":str(qp.relative_to(root)),"queue_sha":h(qp),"queue_sha_type":"sha256_content"},"rules":rows,"required_enforcers":["RULE-011","RULE-012"],"blockers":bad,"next_task":"BEM948-P3-PROVIDER-FAILOVER-LIVE-TEST" if not bad else "BEM948-P2-AUTOREPAIR"}
    z=evid(x)
    if z:x["status"]="BLOCKED";x["blockers"]=sorted(set(bad+z));x["next_task"]="BEM948-P2-AUTOREPAIR"
    return x
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo-root",default=str(ROOT));p.add_argument("--queue",default=str(QDEF));p.add_argument("--out");p.add_argument("--verify");p.add_argument("--strict",action="store_true");a=p.parse_args()
    if a.verify:
        z=evid(j(Path(a.verify)));print(json.dumps({"status":"PASS" if not z else "BLOCKED","violations":z}));raise SystemExit(bool(z))
    root=Path(a.repo_root).resolve();qp=Path(a.queue).resolve();x=make(root,qp,j(qp))
    if a.out:w(Path(a.out).resolve(),x)
    print(json.dumps(x,indent=2));raise SystemExit(a.strict and x["status"]!="PASS")
if __name__=="__main__":main()
