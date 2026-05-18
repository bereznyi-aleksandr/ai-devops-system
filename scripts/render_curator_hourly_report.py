#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
KYIV = timezone(timedelta(hours=3))
OUT = Path("governance/tmp/curator_hourly_report_message.txt")
STATE = Path("governance/state/curator_hourly_report_state.json")
REPORT = Path("governance/reports/curator_hourly_report_runtime.md")
TRANSPORT = Path("governance/transport/results.jsonl")
def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except:
        return {}
def read_events(limit=20):
    if not TRANSPORT.exists():
        return []
    events = []
    for line in TRANSPORT.read_text(encoding="utf-8", errors="ignore").splitlines():
        line=line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except:
            pass
    return events[-limit:]
def event_status(events, key):
    for ev in reversed(events):
        txt = json.dumps(ev, ensure_ascii=False).lower()
        if key in txt:
            return ev.get("status") or ev.get("result") or "seen"
    return "pending"
def mark(ok, pending=False):
    if ok:
        return "✅"
    if pending:
        return "⚠️"
    return "❌"
def row(n, name, essence, status):
    return f"{n:<2} | {name:<18} | {essence:<28} | {status}"
now = datetime.now(KYIV)
report_hour = now.replace(minute=0, second=0, microsecond=0)
events = read_events()
contour = load_json(Path("governance/state/contour_status.json"))
smoke = load_json(Path("governance/state/telegram_send_smoke_result.json"))
hourly = load_json(Path("governance/state/curator_hourly_report_state.json"))
final = load_json(Path("governance/state/bem668_final_readiness_or_exact_blocker.json"))
write_smoke = load_json(Path("governance/state/bem646_post_repair_codex_runner_smoke.json"))
lint = load_json(Path("governance/state/internal_contour_architecture_lint.json"))
provider = load_json(Path("governance/state/bem632_close_provider_route_and_delivery_status.json"))
write_ok = write_smoke.get("status") == "pass" or contour.get("codex_runner_write_channel_status") == "restored"
lint_ok = lint.get("status") == "pass" or contour.get("internal_contour_architecture_status") == "closed"
provider_ok = provider.get("architecture_closed") is True or contour.get("internal_contour_architecture_status") == "closed"
smoke_ok = smoke.get("delivery_confirmed") is True
hourly_ok = hourly.get("telegram_delivery") == "sent"
final_ok = final.get("status") == "production_ready"
rows = [
    (1, "Write-channel", "runner restored", mark(write_ok, True)),
    (2, "Role-bus", "roles and lanes checked", mark(lint_ok, True)),
    (3, "Provider route", "primary/reserve explicit", mark(provider_ok, True)),
    (4, "Telegram smoke", "direct send proof", mark(smoke_ok, True)),
    (5, "Hourly report", "hourly delivery", mark(hourly_ok, True)),
    (6, "Readiness", "final acceptance", mark(final_ok, True)),
]
done = sum(1 for r in rows if r[3] == "✅")
total = len(rows)
percent = round(done * 100 / total)
lines=[]
lines.append("BEM-HOURLY | SYSTEM MONITORING REPORT")
lines.append("Дата: " + report_hour.strftime("%Y-%m-%d | %H:00 (UTC+3)"))
lines.append("")
lines.append(f"Этап: {done}/{total} ({percent}%)")
lines.append(f"Дорожная карта: {done}/{total} ({percent}%)")
lines.append("")
lines.append("```")
lines.append("№  | Наименование       | Краткая суть                 | Статус")
lines.append("---+--------------------+------------------------------+-------")
for r in rows:
    lines.append(row(*r))
lines.append("```")
message = SEP.join(lines) + SEP
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(message, encoding="utf-8")
STATE.parent.mkdir(parents=True, exist_ok=True)
state={"schema_version":"curator_hourly_report_state.v2","status":"rendered","report_hour":report_hour.strftime("%Y-%m-%d | %H:00 (UTC+3)"),"stage_done":done,"stage_total":total,"stage_percent":percent,"roadmap_done":done,"roadmap_total":total,"roadmap_percent":percent,"telegram_delivery":"pending_send","rows":[{"number":r[0],"name":r[1],"essence":r[2],"status":r[3]} for r in rows],"blocker":None}
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Curator Hourly Report Runtime" + SEP + SEP + message, encoding="utf-8")
print(json.dumps({"status":"rendered","hour":state["report_hour"],"done":done,"total":total}, ensure_ascii=False))
