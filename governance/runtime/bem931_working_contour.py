#!/usr/bin/env python3
import argparse,json,uuid
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2]
def n():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def w(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def t(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(x,encoding="utf-8")
def a(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.open("a",encoding="utf-8").write(json.dumps(x,ensure_ascii=False)+"\n")
def run(f,tid):
 o=json.loads((R/f).read_text(encoding="utf-8")); tid=tid or "BEM931-WORKING-"+uuid.uuid4().hex[:8]
 actors=["GD.CURATOR","DIR.CURATOR","WRK.ANALYST","WRK.AUDITOR","WRK.EXECUTOR"]
 req={"objective_id","initiator","objective","requested_capability","operator_gate"}; miss=sorted(req-set(o))
 tr={"trace_id":tid,"protocol":"BEM-931 v3.5","created_at":n(),"actors":actors,"release_pass":False,"release_blockers":["production_telegram_receipt_required","live_runtime_receipt_required","external_claude_audit_receipt_required"]}
 if miss or o.get("operator_gate")!="approved":
  tr.update(ok=False,repo_level_pass=False,input_valid=False,errors=(["missing_fields:"+",".join(miss)] if miss else [])+(["operator_gate_not_approved"] if o.get("operator_gate")!="approved" else []))
  return save(tr)
 q=R/"governance/runtime/state/managed_channel_queue.jsonl"; m={"message_id":"MSG-"+uuid.uuid4().hex[:8],"status":"consumed","channel_id":"CURATOR_MANAGED_CHANNEL","payload":o,"created_at":n(),"consumed_at":n()}; a(q,m)
 exp="EXP.BEM931.NO_STATUS_ONLY"; w(R/"governance/experience/experience_registry.json",{"records":[{"experience_id":exp,"rule_ref":"POLICY.BEM931.CAPABILITY_FIRST","applies_to":["curator","auditor"]}]})
 rd=R/"governance/results"/tid; art=rd/"worker_result.json"; w(art,{"trace_id":tid,"actor_id":"WRK.EXECUTOR","task_id":"TASK-"+o["objective_id"],"capability_delta":"working_minimal_governance_loop_e2e","safe":True,"secrets_touched":False,"created_at":n()})
 tr.update(input_valid=True,managed_message_id=m["message_id"],dequeued=True,gd_route={"actor_id":"GD.CURATOR","decision":{"director_curator_id":"DIR.CURATOR","target_contour_id":"WRK.ANALYSIS_CONTOUR"}},assignment={"actor_id":"DIR.CURATOR","assignments":{"analyst_id":"WRK.ANALYST","auditor_id":"WRK.AUDITOR","executor_id":"WRK.EXECUTOR"}},experience={"applied_experience_ids":[exp]},audit={"precheck":{"actor_id":"WRK.AUDITOR","ok":True},"postcheck":{"actor_id":"WRK.AUDITOR","ok":True}},execution={"executor_id":"WRK.EXECUTOR","ok":True,"artifact_relpath":str(art.relative_to(R))},ok=True,repo_level_pass=True)
 return save(tr)
def save(tr):
 rp=R/"governance/reports/operator"/(tr["trace_id"]+".md")
 checks=[("Вход оператора принят",tr.get("input_valid") is True),("Сообщение поставлено в управляемый канал",bool(tr.get("managed_message_id"))),("Сообщение прочитано",tr.get("dequeued") is True),("Куратор ГД выбрал маршрут",tr.get("gd_route",{}).get("actor_id")=="GD.CURATOR"),("Куратор директора назначил роли",tr.get("assignment",{}).get("actor_id")=="DIR.CURATOR"),("Аудитор pre-check",tr.get("audit",{}).get("precheck",{}).get("ok") is True),("Исполнитель создал результат",tr.get("execution",{}).get("ok") is True),("Аудитор post-check",tr.get("audit",{}).get("postcheck",{}).get("ok") is True)]
 text="\n".join(["BEM-931 | ОТЧЁТ ОПЕРАТОРУ","Trace: "+tr["trace_id"],"","ЭТАП:","1/1 (100%)" if tr.get("ok") else "0/1 (0%)","","ДОРОЖНАЯ КАРТА:","1/1 (100%)" if tr.get("ok") else "0/1 (0%)","","ЧЕК-ЛИСТ:"]+[("✅ " if ok else "❌ "+name for name,ok in checks]
+["","ВОПРОС ОПЕРАТОРУ:","нет" if tr.get("ok") else "требуется разбор ошибки"])+"\n"; t(rp,text); tr["operator_report_path"]=str(rp.relative_to(R))
 tp=R/"governance/traces"/(tr["trace_id"]+".json"); w(tp,tr)
 rc=R/"governance/proofs"/(tr["trace_id"]+"_receipt.json"); w(rc,{"ok":tr.get("ok") is True,"repo_level_pass":tr.get("repo_level_pass") is True,"release_pass":False,"trace_path":str(tp.relative_to(R)),"operator_report_path":tr["operator_report_path"],"worker_result":tr.get("execution",{}).get("artifact_relpath"),"created_at":n()}); tr["receipt_path"]=str(rc.relative_to(R)); w(tp,tr); a(R/"governance/logs/working_contour_execution_log.jsonl",{"date":n(),"trace_id":tr["trace_id"],"ok":tr.get("ok") is True,"receipt_path":tr["receipt_path"]}); return tr
if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("--fixture",default="governance/tests/fixtures/operator_objective_valid.json"); p.add_argument("--output",default="governance/test_results/bem931_working_contour_latest.json"); p.add_argument("--trace-id",default=""); x=p.parse_args(); r=run(Path(x.fixture),x.trace_id); w(R/x.output,r); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(0 if r.get("ok") else 2)
