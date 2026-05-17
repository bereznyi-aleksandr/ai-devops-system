#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
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
def short(text, limit):
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[:max(0, limit-1)].rstrip() + "…"
def pad(text, width):
    value = short(text, width)
    return value + " " * max(0, width - len(value))
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
def make_table(options):
    rows = []
    rows.append("┌────┬──────────────┬──────────────────────┐")
    rows.append("│ №  │ Вариант      │ Отличие / обоснование │")
    rows.append("├────┼──────────────┼──────────────────────┤")
    for opt in options[:4]:
        oid = pad(opt.get("id", "?"), 2)
        title = pad(opt.get("title", ""), 12)
        combo = pad(short(opt.get("difference", ""), 10) + "; " + short(opt.get("rationale", ""), 10), 20)
        rows.append("│ " + oid + " │ " + title + " │ " + combo + " │")
    rows.append("└────┴──────────────┴──────────────────────┘")
    return SEP.join(rows)
def make_details(options):
    rows = []
    for opt in options[:4]:
        oid = str(opt.get("id", "?"))
        rows.append(oid + ") " + str(opt.get("title", "")))
        rows.append("   Отличие: " + short(opt.get("difference", ""), 160))
        rows.append("   Обоснование: " + short(opt.get("rationale", ""), 180))
        if opt.get("impact"):
            rows.append("   Последствие: " + short(opt.get("impact", ""), 160))
        rows.append("")
    return SEP.join(rows).strip()
def build_message(pkg):
    stage = pkg.get("stage") or {"done":1,"total":1}
    roadmap = pkg.get("roadmap") or {"done":1,"total":1}
    sd = stage.get("done",1); st = stage.get("total",1)
    rd = roadmap.get("done",1); rt = roadmap.get("total",1)
    opts = pkg.get("options") or []
    lines = [str(pkg.get("bem","BEM-MAILBOX")) + " | " + str(pkg.get("title","OPERATOR DECISION REQUIRED")) + " | workflow_runtime", "", "Этап: " + str(sd) + "/" + str(st) + " (" + str(pct(sd,st)) + "%)", "Дорожная карта: " + str(rd) + "/" + str(rt) + " (" + str(pct(rd,rt)) + "%)", "", "Чек-лист:"]
    for item in (pkg.get("checklist") or ["Claude/GPT обсуждение завершено", "Decision package подготовлен", "Требуется решение оператора"])[:6]:
        item = str(item).strip()
        lines.append(item if item.startswith(("✅","⚠️","❌")) else "✅ " + item)
    lines += ["", "Вопрос:", str(pkg.get("question","")).strip(), "", "Таблица сравнения:", make_table(opts), "", "Детали по вариантам:", make_details(opts)]
    rec = pkg.get("recommendation") or {}
    if rec:
        lines += ["", "Рекомендация аудиторов:", "Вариант " + str(rec.get("option_id","?")) + ": " + str(rec.get("rationale",""))]
    lines += ["", "Как ответить:", str(pkg.get("reply_format","Напиши 1, 2, 3 или свой вариант текстом.")), "", "Что будет после решения:", "Пакет решения передаётся куратору, затем во внутренний контур."]
    return SEP.join(lines).strip() + SEP
state = load_json(STATE_PATH, {})
processed = set(state.get("processed_items", []))
QUEUE_DIR.mkdir(parents=True, exist_ok=True)
candidates = sorted([p for p in QUEUE_DIR.glob("*.json") if p.is_file()], key=lambda p: str(p))
picked_path = None; pkg = None
for path in candidates:
    if str(path) not in processed:
        picked_path = path; pkg = load_json(path, {}); break
TMP_DIR.mkdir(parents=True, exist_ok=True)
if picked_path is None:
    result = {"picked": False, "send": False, "queue_file": None, "reason": "no_new_decision_package"}
    MSG_PATH.write_text("", encoding="utf-8")
else:
    ok, reason = validate(pkg)
    if ok:
        message = build_message(pkg)
        result = {"picked": True, "send": True, "queue_file": str(picked_path), "decision_id": pkg.get("decision_id"), "reason": "valid_decision_package", "message": message}
        MSG_PATH.write_text(message, encoding="utf-8")
    else:
        result = {"picked": True, "send": False, "queue_file": str(picked_path), "reason": "invalid_decision_package:" + str(reason)}
        MSG_PATH.write_text("", encoding="utf-8")
PICK_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + SEP, encoding="utf-8")
print(json.dumps({"picked": result.get("picked"), "send": result.get("send"), "reason": result.get("reason"), "queue_file": result.get("queue_file")}, ensure_ascii=False))
