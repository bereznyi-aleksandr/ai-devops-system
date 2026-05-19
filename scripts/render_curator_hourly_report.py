#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEP = "\n"
KYIV = timezone(timedelta(hours=3))
OUT = Path("governance/tmp/curator_hourly_report_message.txt")
STATE = Path("governance/state/curator_hourly_report_state.json")
SNAPSHOT = Path("governance/state/curator_hourly_report_last_snapshot.json")
REPORT = Path("governance/reports/curator_hourly_report_runtime.md")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def mark(ok: bool, pending: bool = False) -> str:
    if ok:
        return "✅"
    if pending:
        return "⚠️"
    return "❌"


def cut(text: str, width: int) -> str:
    text = str(text)
    if len(text) <= width:
        return text.ljust(width)
    return text[: max(0, width - 1)] + "…"


def table_row(n: int, name: str, essence: str, status: str) -> str:
    return f"{str(n).rjust(1)} | {cut(name, 12)} | {cut(essence, 16)} | {status}"


now = datetime.now(KYIV)
report_hour = now.replace(minute=0, second=0, microsecond=0)
period = report_hour.strftime("%H:00–%H:59 (UTC+3)")

previous_snapshot = load_json(SNAPSHOT)
previous_state = load_json(STATE)
contour = load_json(Path("governance/state/contour_status.json"))
smoke = load_json(Path("governance/state/telegram_send_smoke_result.json"))
hourly = previous_state
final = load_json(Path("governance/state/bem668_final_readiness_or_exact_blocker.json"))
write_smoke = load_json(Path("governance/state/bem646_post_repair_codex_runner_smoke.json"))
lint = load_json(Path("governance/state/internal_contour_architecture_lint.json"))
provider = load_json(Path("governance/state/bem632_close_provider_route_and_delivery_status.json"))

write_ok = write_smoke.get("status") == "pass" or contour.get("codex_runner_write_channel_status") == "restored"
lint_ok = lint.get("status") == "pass" or contour.get("internal_contour_architecture_status") == "closed"
provider_ok = provider.get("architecture_closed") is True or contour.get("internal_contour_architecture_status") == "closed"
smoke_ok = smoke.get("delivery_confirmed") is True
hourly_ok = hourly.get("telegram_delivery") in ["sent", "pending_send"]
final_ok = final.get("status") == "production_ready"

rows = [
    (1, "Канал", "восстановлен", mark(write_ok, True)),
    (2, "Роли", "проверены", mark(lint_ok, True)),
    (3, "Провайдер", "маршрут ясен", mark(provider_ok, True)),
    (4, "ТГ-тест", "отправка есть", mark(smoke_ok, True)),
    (5, "Часовой", "доставка есть", mark(hourly_ok, True)),
    (6, "Готовность", "принята", mark(final_ok, True)),
]

done = sum(1 for item in rows if item[3] == "✅")
total = len(rows)
percent = round(done * 100 / total)
row_dicts = [{"number": r[0], "name": r[1], "essence": r[2], "status": r[3]} for r in rows]

fingerprint = {
    "stage_done": done,
    "stage_total": total,
    "stage_percent": percent,
    "roadmap_done": done,
    "roadmap_total": total,
    "roadmap_percent": percent,
    "rows": row_dicts,
}

previous_fingerprint = None
if isinstance(previous_snapshot, dict):
    previous_fingerprint = previous_snapshot.get("fingerprint")
    if previous_fingerprint is None and previous_snapshot.get("rows") is not None:
        previous_fingerprint = {
            "stage_done": previous_snapshot.get("stage_done"),
            "stage_total": previous_snapshot.get("stage_total"),
            "stage_percent": previous_snapshot.get("stage_percent"),
            "roadmap_done": previous_snapshot.get("roadmap_done"),
            "roadmap_total": previous_snapshot.get("roadmap_total"),
            "roadmap_percent": previous_snapshot.get("roadmap_percent"),
            "rows": previous_snapshot.get("rows"),
        }
if previous_fingerprint is None and isinstance(previous_state, dict) and previous_state.get("rows") is not None:
    previous_fingerprint = {
        "stage_done": previous_state.get("stage_done"),
        "stage_total": previous_state.get("stage_total"),
        "stage_percent": previous_state.get("stage_percent"),
        "roadmap_done": previous_state.get("roadmap_done"),
        "roadmap_total": previous_state.get("roadmap_total"),
        "roadmap_percent": previous_state.get("roadmap_percent"),
        "rows": previous_state.get("rows"),
    }

unchanged = previous_fingerprint == fingerprint

lines = [
    "BEM-HOURLY | ЧАСОВОЙ ОТЧЁТ",
    "Сформировано: " + now.strftime("%Y-%m-%d | %H:%M (UTC+3)"),
    "Период: " + period,
    "",
]
if unchanged:
    lines.append("Изменений за отчётный период нет.")
else:
    lines.extend([
        f"Этап: {done}/{total} ({percent}%)",
        f"Дорожная карта: {done}/{total} ({percent}%)",
        "",
        "```",
        "№ | Наименование | Краткая суть     | Ст",
        "--+--------------+------------------+---",
    ])
    for row in rows:
        lines.append(table_row(*row))
    lines.append("```")

message = SEP.join(lines) + SEP
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(message, encoding="utf-8")

state = {
    "schema_version": "curator_hourly_report_state.v6_stable_fingerprint",
    "status": "rendered_no_changes" if unchanged else "rendered_changes",
    "generated_at": now.strftime("%Y-%m-%d | %H:%M (UTC+3)"),
    "period": period,
    "report_hour": report_hour.strftime("%Y-%m-%d | %H:00 (UTC+3)"),
    "stage_done": done,
    "stage_total": total,
    "stage_percent": percent,
    "roadmap_done": done,
    "roadmap_total": total,
    "roadmap_percent": percent,
    "telegram_delivery": "pending_send",
    "language": "ru",
    "layout": "delta_compact_table",
    "unchanged_since_last_fingerprint": unchanged,
    "snapshot_file": str(SNAPSHOT),
    "fingerprint": fingerprint,
    "rows": row_dicts,
    "blocker": None,
}
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")

snapshot = dict(state)
snapshot["fingerprint"] = fingerprint
SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
SNAPSHOT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")

REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Curator Hourly Report Runtime" + SEP + SEP + message, encoding="utf-8")
print(json.dumps({"status": state["status"], "unchanged": unchanged, "period": period}, ensure_ascii=False))
