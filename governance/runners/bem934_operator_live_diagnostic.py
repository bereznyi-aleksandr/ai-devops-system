#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT=Path(".")
paths={
 "queue":ROOT/"governance/roadmap/ACTIVE_QUEUE.json",
 "recon":ROOT/"governance/proofs/BEM934_live_state_reconciliation_receipt.json",
 "router":ROOT/"governance/proofs/BEM932_provider_router_tg_818730867_20260618T105741Z.json",
 "transport":ROOT/"governance/transport/results.jsonl",
 "report":ROOT/"governance/reports/tg_818730867_20260618T105741Z.md",
 "evidence":ROOT/"governance/proofs/evidence/BEM934_operator_telegram_tg_818730867_20260618T105741Z.jpg",
 "out":ROOT/"governance/proofs/BEM934_operator_live_finalization_diagnostic.json",
}
TRACE="tg_818730867_20260618T105741Z"

def loadj(p:Path)->dict[str,Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def loadjl(p:Path)->list[dict[str,Any]]:
    out=[]
    for n,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        try:
            value=json.loads(line)
            if isinstance(value,dict): out.append(value)
        except Exception:
            out.append({"_parse_error_line":n,"_raw":line[:200]})
    return out

def git_blob_sha(data:bytes)->str:
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def main()->None:
    q=loadj(paths["queue"]); r=loadj(paths["recon"]); ro=loadj(paths["router"])
    ts=loadjl(paths["transport"])
    rp=paths["report"].read_text(encoding="utf-8")
    ev=paths["evidence"].read_bytes()
    matching=[x for x in ts if x.get("trace_id")==TRACE]
    completed=[x for x in matching if x.get("status")=="completed" and x.get("blocker") is None]
    checks={
      "queue_current_live":q.get("current_task")=="BEM934-LIVE-TEST",
      "recon_status_pass":r.get("status")=="PASS",
      "recon_release_not_promoted":r.get("release_promoted") is False,
      "recon_live_not_closed":r.get("live_task_closed") is False,
      "evidence_exists":paths["evidence"].exists(),
      "evidence_jpeg":ev[:2]==b"\xff\xd8" and ev[-2:]==b"\xff\xd9",
      "evidence_size_min":len(ev)>=5000,
      "router_status_pass":ro.get("status")=="PASS",
      "router_trace":ro.get("trace_id")==TRACE,
      "router_provider":ro.get("provider_selected")=="claude_code",
      "router_target":ro.get("target_workflow_id")=="claude.yml",
      "router_dispatch":ro.get("dispatch_result")=="success",
      "router_message_id":str(ro.get("message_id","")).strip()!="",
      "transport_completed_any_role":bool(completed),
      "transport_completed_executor":any(x.get("role")=="executor" for x in completed),
      "transport_provider_claude":any(x.get("provider")=="claude" for x in completed),
      "report_length":len(rp.strip())>=200,
      "report_has_pass": "PASS" in rp,
      "report_has_fail": "FAIL" in rp,
      "report_has_invariant": "инвариант" in rp.lower(),
    }
    data={
      "status":"PASS" if all(checks.values()) else "BLOCKED",
      "task_id":"BEM934-LIVE-TEST-DIAGNOSTIC",
      "checks":checks,
      "failed_checks":[k for k,v in checks.items() if not v],
      "evidence":{"size":len(ev),"sha256":hashlib.sha256(ev).hexdigest(),"git_blob_sha":git_blob_sha(ev)},
      "router_observed":ro,
      "matching_transport_records":matching,
      "report":{"path":str(paths["report"]),"length":len(rp),"preview":rp[:500]},
      "release_promoted":False,
    }
    paths["out"].write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
