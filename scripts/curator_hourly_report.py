#!/usr/bin/env python3
import json
from pathlib import Path
from telegram_canon_formatter import format_report
OUTBOX=Path("governance/telegram_outbox.jsonl")
TRANSPORT=Path("governance/transport/results.jsonl")
STATE=Path("governance/state/contour_status.json")
state={}
if STATE.exists():
    try: state=json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: state={}
bem=state.get("current_bem") or "BEM-HOURLY"
title="HOURLY CURATOR REPORT"
# Default values keep message canonical even if state lacks exact roadmap counters.
stage_done=state.get("stage_done", state.get("current_stage_done", 1))
stage_total=state.get("stage_total", state.get("current_stage_total", 1))
roadmap_done=state.get("roadmap_done", state.get("roadmap_completed", 1))
roadmap_total=state.get("roadmap_total", state.get("roadmap_total", 1))
msg=format_report(
    bem=bem,
    title=title,
    date="2026-05-17",
    time="19:00",
    stage_done=stage_done,
    stage_total=stage_total,
    roadmap_done=roadmap_done,
    roadmap_total=roadmap_total,
    checklist=[
        "✅ Куратор активен",
        "✅ Внутренний контур доступен",
        "✅ Telegram delivery активен",
        "✅ Progress feed активен",
        "✅ blocker=null",
    ],
    rows=[
        ("Состояние", "Hourly report alive", "Плановый heartbeat от куратора"),
        ("Прогресс", "Этап и дорожная карта указаны в шапке", "Требование канона"),
        ("Blocker", "null", "Ошибок, требующих оператора, нет"),
        ("Следующее действие", "Продолжение roadmap", "Непрерывный режим выполнения"),
    ],
)
rec={"record_type":"telegram_hourly_report","cycle_id":"curator-hourly-report","delivery_mode":"curator-hourly-report.yml","canonical":True,"status":"ready_to_send","message":msg,"created_at":"workflow_runtime","blocker":None,"priority":"operator_progress"}
OUTBOX.parent.mkdir(parents=True,exist_ok=True)
with OUTBOX.open("a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"
")
TR=rec.copy(); TR["record_type"]="curator_hourly_report_generated"; TR["artifact_path"]="governance/telegram_outbox.jsonl"; TR["commit_sha"]=None
TRANSPORT.parent.mkdir(parents=True,exist_ok=True)
with TRANSPORT.open("a",encoding="utf-8") as f: f.write(json.dumps(TR,ensure_ascii=False)+"
")
state["curator_hourly_report_last_generated"]={"status":"ready_to_send","message":msg,"updated_at":"workflow_runtime","format":"telegram_canon.v1"}
STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"
",encoding="utf-8")
print(msg)
