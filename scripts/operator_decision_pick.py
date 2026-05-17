#!/usr/bin/env python3
import json
from pathlib import Path

NL = "\n"
QUEUE_DIR = Path("governance/operator_decision_queue")
STATE_PATH = Path("governance/state/operator_decision_dispatcher_state.json")
TMP_DIR = Path("governance/tmp")
PICK_PATH = TMP_DIR / "operator_decision_pick.json"
MSG_PATH = TMP_DIR / "operator_decision_message.txt"

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def pct(done, total):
    try:
        done = int(done); total = int(total)
        return 0 if total <= 0 else round(done * 100 / total)
    except Exception:
        return 0

def validate(pkg):
    if not pkg.get("decision_id") or not pkg.get("question"):
        return False, "missing_decision_id_or_question"
    opts = pkg.get("options") or []
    if len(opts) < 2:
        return False, "need_at_least_two_options"
    for opt in opts:
        if not opt.get("id") or not opt.get("title") or not opt.get("difference") or not opt.get("rationale"):
            return False, "option_missing_required_fields"
    return True, None

def short(text, limit):
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[:max(0, limit - 1)].rstrip() + "…"

def pad(text, width):
    text = short(text, width)
    return text + " " * max(0, width - len(text))

def make_table(options):
    # Narrow fixed-width table for Telegram mobile.
    rows = []
    rows.append("┌────┬──────────────┬──────────────────────┐")
    rows.append("│ №  │ Вариант      │ Отличие / обоснование │")
    rows.append("├────┼──────────────┼──────────────────────┤")
    for opt in options[:4]:
        oid = pad(opt.get("id", "?"), 2)
        title = pad(opt.get("title", ""), 12)
        diff = short(opt.get("difference", ""), 10)
        rat = short(opt.get("rationale", ""), 10)
        combo = pad(diff + "; " + rat, 20)
        rows.append("│ " + oid + " │ " + title + " │ " + combo + " │")
    rows.append("└────┴──────────────┴──────────────────────┘")
    return NL.join(rows)

def make_details(options):
    parts = []
    for opt in options[:4]:
        oid = str(opt.get("id", "?"))
        parts.append(oid + ") " + str(opt.get("title", "")))
        parts.append("   Отличие: " + short(opt.get("difference", ""), 160))
        parts.append("   Обоснование: " + short(opt.get("rationale", ""), 180))
        if opt.get("impact"):
            parts.append("   Последствие: " + short(opt.get("impact", ""), 160))
        parts.append("")
    return NL.join(parts).strip()

def build_message(pkg):
    stage = pkg.get("stage") or {"done": 1, "total": 1}
    roadmap = pkg.get("roadmap") or {"done": 1, "total": 1}
    sd = stage.get("done", 1); st = stage.get("total", 1)
    rd = roadmap.get("done", 1); rt = roadmap.get("total", 1)
    bem = pkg.get("bem", "BEM-MAILBOX")
    title = pkg.get("title", "OPERATOR DECISION REQUIRED")
    opts = pkg.get("options") or []
    lines = [
        f"{bem} | {title} | workflow_runtime",
        "",
        f"Этап: {sd}/{st} ({pct(sd, st)}%)",
        f"Дорожная карта: {rd}/{rt} ({pct(rd, rt)}%)",
        "",
        "Чек-лист:",
    ]
    checklist = pkg.get("checklist") or ["Claude/GPT обсуждение завершено", "Decision package подготовлен", "Требуется решение оператора"]
    for item in checklist[:6]:
        item = str(item).strip()
        lines.append(item if item.startswith(("✅", "⚠️", "❌")) else "✅ " + item)
    lines.extend(["", "Вопрос:", str(pkg.get("question", "")).strip(), "", "Таблица сравнения:", make_table(opts), "", "Детали по вариантам:", make_details(opts)])
    rec = pkg.get("recommendation") or {}
    if rec:
        lines.extend(["", "Рекомендация аудиторов:", "Вариант " + str(rec.get("option_id", "?")) + ": " + str(rec.get("rationale", ""))])
    lines.extend(["", "Как ответить:", pkg.get("reply_format", "Напиши 1, 2, 3 или свой вариант текстом."), "", "Что будет после решения:", "Пакет решения передаётся куратору, затем во внутренний контур."])
    return NL.join(lines).strip() + NL

state = load_json(STATE_PATH, {})
processed = set(state.get("processed_items", []))
QUEUE_DIR.mkdir(parents=True, exist_ok=True)
candidates = sorted([p for p in QUEUE_DIR.glob("*.json") if p.is_file()], key=lambda p: str(p))
picked_path = None
pkg = None
for path in candidates:
    if str(path) not in processed:
        picked_path = path
        pkg = load_json(path, {})
        break

TMP_DIR.mkdir(parents=True, exist_ok=True)
if picked_path is None:
    pick = {"picked": False, "send": False, "queue_file": None, "reason": "no_new_decision_package"}
    MSG_PATH.write_text("", encoding="utf-8")
else:
    ok, reason = validate(pkg)
    if ok:
        message = build_message(pkg)
        pick = {"picked": True, "send": True, "queue_file": str(picked_path), "decision_id": pkg.get("decision_id"), "reason": "valid_decision_package", "message": message}
        MSG_PATH.write_text(message, encoding="utf-8")
    else:
        pick = {"picked": True, "send": False, "queue_file": str(picked_path), "reason": "invalid_decision_package:" + str(reason)}
        MSG_PATH.write_text("", encoding="utf-8")
PICK_PATH.write_text(json.dumps(pick, ensure_ascii=False, indent=2) + NL, encoding="utf-8")
print(json.dumps({"picked": pick.get("picked"), "send": pick.get("send"), "reason": pick.get("reason"), "queue_file": pick.get("queue_file")}, ensure_ascii=False))
