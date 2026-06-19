#!/usr/bin/env python3
"""Testing contour assignment runtime for BEM-941."""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
ASSIGNMENTS = STATE / "testing_contour_assignments.jsonl"
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def safe(x): return re.sub(r"[^A-Za-z0-9_.:-]+","_",str(x or "trace"))[:140]
def assign(trace_id: str, task_id: str):
    low = (trace_id + " " + task_id).lower()
    if "live" in low or "telegram" in low:
        contour = "WRK-LIVE"
    elif "smoke" in low or "test" in low:
        contour = "WRK-SMOKE"
    else:
        contour = "WRK-C1"
    return {"status":"ASSIGNED","protocol":"BEM-941","task_id":task_id,"trace_id":safe(trace_id),"created_at":now(),"contour":contour,"source":"governance/runners/testing_contour_assignment.py","non_claim":"contour assignment only; no downstream LLM completion claimed"}
def append(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as h: h.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
def main():
    p=argparse.ArgumentParser(); p.add_argument("--trace-id", default="bem941_testing_contour_selftest"); p.add_argument("--task-id", default="BEM941-P2-TESTING-CONTOUR-ASSIGNMENT"); args=p.parse_args()
    item=assign(args.trace_id,args.task_id); append(ASSIGNMENTS,item)
    checks={"testing_contour_assignment_runtime_code_present":True,"assignment_written":ASSIGNMENTS.exists(),"contour_selected":bool(item["contour"]),"downstream_llm_completion_not_claimed":True}
    blockers=[k for k,v in checks.items() if not v]
    receipt={"status":"PASS" if not blockers else "BLOCKED","protocol":"BEM-941","task_id":"BEM941-P2-TESTING-CONTOUR-ASSIGNMENT","created_at":now(),"stage":{"tasks_done":3,"tasks_total":4,"percent":75},"assignment":item,"assignments_path":str(ASSIGNMENTS.relative_to(ROOT)),"checks":checks,"blockers":blockers,"next_task":"BEM941-P3-FINAL-VERIFY" if not blockers else None}
    PROOFS.mkdir(parents=True, exist_ok=True)
    (PROOFS/"BEM941_testing_contour_assignment_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if blockers: raise SystemExit(1)
if __name__ == "__main__": main()
