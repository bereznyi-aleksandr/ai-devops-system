#!/usr/bin/env python3
"""BEM-950 provider router: provider-neutral and cost-policy aware."""
import argparse,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"governance/config/provider_config.json"
KEYS=("provider_selected","fallback_reason","decision_source","trace_id","ttl_seconds","stale_ignored")
def load():
 data=json.loads(CONFIG.read_text(encoding="utf-8"))
 if not isinstance(data,dict):raise ValueError("provider_config.json must be a JSON object")
 return data
def enabled(config):
 providers=config.get("providers",{})
 if not isinstance(providers,dict):raise ValueError("providers must be an object")
 out=[(k,v) for k,v in providers.items() if isinstance(k,str) and isinstance(v,dict) and v.get("enabled") is True]
 if not out:raise RuntimeError("no enabled provider is configured")
 return sorted(out,key=lambda x:(int(x[1].get("priority",999)),x[0]))
def forced(task):
 t=task.lower()
 return any(s in t for s in ("force-fallback","force fallback","quota-fallback","quota fallback"))
def main(role,task,trace_id):
 config=load(); selected=enabled(config)[0][0]
 providers=config["providers"]; blocked=any(isinstance(v,dict) and v.get("status")=="DISABLED_BY_COST_POLICY" for v in providers.values())
 reason="fallback_blocked_cost_policy" if forced(task) and blocked else ("fallback_unavailable" if forced(task) else None)
 source="cost_policy" if reason=="fallback_blocked_cost_policy" else ("operator_forced_fallback" if reason else "default")
 return {"provider_selected":selected,"fallback_reason":reason,"decision_source":source,"trace_id":trace_id,"ttl_seconds":int(config.get("ttl_seconds",1800)),"stale_ignored":False}
def cli():
 p=argparse.ArgumentParser();p.add_argument("--role",required=True,choices=("curator","analyst","auditor","executor"));p.add_argument("--task",default="");p.add_argument("--trace-id",default="")
 a=p.parse_args(); trace=a.trace_id or f"trace_{int(time.time())}"
 print(json.dumps(main(a.role,a.task,trace),ensure_ascii=False,sort_keys=True))
if __name__=="__main__":cli()
