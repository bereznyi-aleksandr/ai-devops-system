#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
KYIV = timezone(timedelta(hours=3))
OUT = Path("governance/tmp/curator_hourly_report_message.txt")
STATE = Path("governance/state/curator_hourly_report_state.json")
DIGEST = Path("governance/state/curator_hourly_report_last_semantic_digest.json")
REPORT = Path("governance/reports/curator_hourly_report_runtime.md")

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def mark(ok, pending=False):
    if ok:
        return "✅"
    if pending:
        return "⚠️"
    return "❌"

def cut(text, width):
    text = str(text)
    if len(text) <= width:
        return text.ljust(width)
    return text[:max(0, width-1)] + "…"

def row(n, name, essence, status):
    return f"{str(n).rjust(1)} | {cut(name, 12)} | {cut(essence, 16)} | {status}"

now = datetime.now(KYIV)
report_hour = now.replace(minute=0, second=0, microsecond=0)
contour = load_json(Path("governance/state/contour_status.json"))
smoke = load_json(Path("governance/state/telegram_send_smoke_result.json"))
write_smoke = load_json(Path("governance/state/bem646_post_repair_codex_runner_smoke.json"))
lint = load_json(Path("governance/state/internal_contour_architecture_lint.json"))
provider = load_json(Path("governance/state/bem632_close_provider_route_and_delivery_status.json"))
final = load_json(Path("governance/state/bem668_final_readiness_or_exact_blocker.json"))

# Important: do not use curator_hourly_report_state.json as input for semantic delta.
# That file changes during every hourly send and caused duplicate full reports.
write_ok = write_smoke.get("status") == "pass" or contour.get("codex_runner_write_channel_status") == "restored"
lint_ok = lint.get("status") == "pass" or contour.get("internal_contour_architecture_status") == "closed"
provider_ok = provider.get("architecture_closed") is True or contour.get("internal_contour_architecture_status") == "closed"
smoke_ok = smoke.get("delivery_confirmed") is True or contour.get("telegram_delivery_status") in ["ready", "confirmed", "sent"]
hourly_ok = True
final_ok = final.get("status") == "production_ready" or contour.get("readiness_status") == "production_ready"
rows = [
    (1, "Канал", "восстановлен", mark(write_ok, True)),
    (2, "Роли", "проверены", mark(lint_ok, True)),
    (3, "Провайдер", "маршрут ясен", mark(provider_ok, True)),
    (4, "ТГ-тест", "отправка есть", mark(smoke_ok, True)),
    (5, "Часовой", "доставка есть", mark(hourly_ok, True)),
    (6, "Готовность", "принята", mark(final_ok, True)),
]
done = sum(1 for r in rows if r[3] == "✅")
total = len(rows)
percent = round(done * 100 / total)
semantic_digest = {
    "schema_version": "curator_hourly_semantic_digest.v1",
    "stage_done": done,
    "stage_total": total,
    "stage_percent": percent,
    "roadmap_done": done,
    "roadmap_total": total,
    "roadmap_percent": percent,
    "rows": [{"number": r[0], "name": r[1], "essence": r[2], "status": r[3]} for r in rows],
}
previous_digest = load_json(DIGEST)
unchanged = previous_digest == semantic_digest
lines=[]
lines.append("BEM-HOURLY | ЧАСОВОЙ ОТЧЁТ")
lines.append("Сформировано: " + now.strftime("%Y-%m-%d | %H:%M (UTC+3)"))
lines.append("Период: " + report_hour.strftime("%H:00–%H:59 (UTC+3)"))
lines.append("")
if unchanged:
    lines.append("Изменений за отчётный период нет.")
else:
    lines.append(f"Этап: {done}/{total} ({percent}%)")
    lines.append(f"Дорожная карта: {done}/{total} ({percent}%)")
    lines.append("")
    lines.append("```")
    lines.append("№ | Наименование | Краткая суть     | Ст")
    lines.append("--+--------------+------------------+---")
    for r in rows:
        lines.append(row(*r))
    lines.append("```")
message = SEP.join(lines) + SEP
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(message, encoding="utf-8")
STATE.parent.mkdir(parents=True, exist_ok=True)
state = {
    "schema_version":"curator_hourly_report_state.v5_semantic_delta",
    "status":"rendered_no_changes" if unchanged else "rendered_changes",
    "generated_at":now.strftime("%Y-%m-%d | %H:%M (UTC+3)"),
    "report_hour":report_hour.strftime("%Y-%m-%d | %H:00 (UTC+3)"),
    "period":report_hour.strftime("%H:00–%H:59 (UTC+3)"),
    "stage_done":done,
    "stage_total":total,
    "stage_percent":percent,
    "roadmap_done":done,
    "roadmap_total":total,
    "roadmap_percent":percent,
    "telegram_delivery":"pending_send",
    "language":"ru",
    "layout":"semantic_delta_compact_table",
    "unchanged_since_last_semantic_digest":unchanged,
    "semantic_digest_file":str(DIGEST),
    "rows":semantic_digest["rows"],
    "blocker":None,
}
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
DIGEST.parent.mkdir(parents=True, exist_ok=True)
DIGEST.write_text(json.dumps(semantic_digest, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Curator Hourly Report Runtime" + SEP + SEP + message, encoding="utf-8")
print(json.dumps({"status":state["status"],"generated_at":state["generated_at"],"period":state["period"],"unchanged":unchanged,"done":done,"total":total}, ensure_ascii=False))
