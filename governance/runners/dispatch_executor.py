#!/usr/bin/env python3
"""BEM-948 fail-closed planned-to-dispatch executor.

Only one explicitly requested trace may be dispatched. HTTP 204 is recorded as
"dispatched", never as executed/completed work.
"""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
PROCESSED = STATE / "dispatch_processed.jsonl"
EXECUTED = STATE / "dispatch_executed.jsonl"
PROOF = ROOT / "governance" / "proofs" / "BEM948_dispatch_executor_receipt.json"
CONFIG = ROOT / "governance" / "config" / "provider_config.json"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def rows(path):
    out=[]
    if not path.exists():
        return out
    for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value=json.loads(raw)
        except json.JSONDecodeError as exc:
            value={"_invalid":"json","_line":n,"_error":str(exc)}
        out.append(value if isinstance(value,dict) else {"_invalid":"non_object","_line":n})
    return out

def key(item):
    return str(item.get("dispatch_id") or item.get("trace_id") or item.get("id") or "")

def append(path, items):
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a",encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")

def write_receipt(payload):
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    PROOF.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def content_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def request_dispatch(token, repo, api, workflow, inputs):
    request=urllib.request.Request(
        f"{api.rstrip('/')}/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref":"main","inputs":inputs},ensure_ascii=False).encode(),
        method="POST",
        headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","Content-Type":"application/json","User-Agent":"ai-devops-system-bem948"},
    )
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            return int(response.status), response.read().decode("utf-8",errors="replace")[:500]
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8",errors="replace")[:500]
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        return None,str(exc)[:500]

def blocked(trace, reason, seen, skipped):
    payload={
        "status":"BLOCKED","protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),
        "processed_source":"governance/state/dispatch_processed.jsonl",
        "executed_output":"governance/state/dispatch_executed.jsonl",
        "trace_filter":trace,"dispatched_count":0,"failed_count":0,"skipped_count":skipped,
        "dispatches":[],"checks":{
            "trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,
            "http_204_means_dispatched_not_completed":True,"sha_type_explicit":True
        },"blockers":[reason],"next_task":"BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR","processed_items_seen":seen
    }
    write_receipt(payload)
    return payload

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--trace-id",required=True)
    parser.add_argument("--max",type=int,default=1)
    args=parser.parse_args()
    trace=args.trace_id.strip()
    if not trace:
        raise SystemExit("trace_id_required")
    source=rows(PROCESSED)
    prior={key(x) for x in rows(EXECUTED) if key(x)}
    eligible=[]
    skipped=0
    for item in source:
        if (item.get("_invalid") or item.get("status")!="processed" or item.get("dispatch_result")!="planned"
            or str(item.get("trace_id") or item.get("dispatch_id") or "")!=trace or key(item) in prior):
            skipped+=1
            continue
        eligible.append(item)
        if len(eligible)>=max(1,args.max):
            break
    if not eligible:
        blocked(trace,"matching_planned_dispatch_absent",len(source),skipped)
        raise SystemExit(1)
    try:
        config=json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        blocked(trace,f"provider_config_unavailable:{exc}",len(source),skipped)
        raise SystemExit(1)
    providers=config.get("providers",{}) if isinstance(config,dict) else {}
    token=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.aetenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    repo=os.getenv("GITHUB_REPOSITORY","")
    api=os.getenv("GITHUB_API_URL","https://api.github.com")
    outcomes=[]
    for item in eligible:
        payload=item.get("payload") if isinstance(item.get("payload"),dict) else {}
        provider=str(item.get("provider_selected") or item.get("provider") or "")
        workflow=str(item.get("target_workflow_id") or "")
        pconf=providers.get(provider) if isinstance(providers,dict) else None
        record={
            "protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),
            "dispatch_id":key(item),"trace_id":trace,
            "logical_role":str(item.get("logical_role") or item.get("role") or "curator"),
            "provider_selected":provider,"target_workflow_id":workflow,
            "source_processed_sha256":content_hash(item),"source_processed_sha256_type":"sha256_content",
            "dispatch_result":"failed","http_status":None,"blocker":None
        }
        if not isinstance(pconf,dict):
            record["blocker"]="provider_missing"
        elif pconf.get("enabled") is not True:
            record["blocker"]="provider_disabled"
        elif pconf.get("workflow_id") != workflow:
            record["blocker"]="target_workflow_mismatch"
        elif not token:
            record["blocker"]="github_token_missing"
        elif not repo:
            record["blocker"]="github_repository_missing"
        else:
            inputs={
                "role":record["logical_role"],
                "provider":"claude" if provider=="claude_code" else provider,
                "trace_id":trace,
                "cycle_id":str(payload.get("cycle_id") or item.get("cycle_id") or f"dispatch_{trace}"),
                "task_type":str(payload.get("task_type") or "default_development"),
                "task":str(payload.get("task") or f"Governance dispatch {trace}")
            }
            record["inputs"]=inputs
            status, body=request_dispatch(token,repo,api,workflow,inputs)
            record["http_status"]=status
            record["response_excerpt"]=body
            if status==204:
                record["dispatch_result"]="dispatched"
            else:
                record["blocker"]=f"workflow_dispatch_http_{status if status is not None else 'network_error'}"
        outcomes.append(record)
    append(EXECUTED,outcomes)
    failures=[x for x in outcomes if x["dispatch_result"]!="dispatched"]
    receipt={
        "status":"PASS" if outcomes and not failures else "BLOCKED",
        "protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),
        "processed_source":"governance/state/dispatch_processed.jsonl",
        "executed_output":"governance/state/dispatch_executed.jsonl",
        "trace_filter":trace,"dispatched_count":sum(x["dispatch_result"]=="dispatched" for x in outcomes),
        "failed_count":len(failures),"skipped_count":skipped,"dispatches":outcomes,
        "checks":{
            "trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,
            "http_dispatch_attempted":nool(outcomes),"http_204_means_dispatched_not_completed":True,
            "sha_type_explicit":True
        },
        "blockers":[x["blocker"] for x in failures if x.get("blocker")],
        "next_task":"BEM948-P0-LIVE-OBJECT-E2E" if not failures else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"
    }
    write_receipt(receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt["status"]!="PASS":
        raise SystemExit(1)

if __name__=="__main__":
    main()
