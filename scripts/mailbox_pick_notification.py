#!/usr/bin/env python3
import json
from pathlib import Path

MAILBOX_DIRS = [Path("governance/audit_mailbox/claude_to_gpt"), Path("governance/audit_mailbox/gpt_to_claude")]
STATE_PATH = Path("governance/state/mailbox_dispatcher_state.json")
TMP_DIR = Path("governance/tmp")
PICK_PATH = TMP_DIR / "mailbox_pick.json"
MSG_PATH = TMP_DIR / "mailbox_message.txt"

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def title_from_markdown(path):
    for line in read_text(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:120]
    return path.name

def infer_sender_recipient(path):
    s = str(path)
    if "claude_to_gpt" in s:
        return "Claude", "GPT"
    if "gpt_to_claude" in s:
        return "GPT", "Claude"
    return "unknown", "unknown"

def compact_path(path):
    text = str(path)
    return text if len(text) <= 90 else text[:42] + "…" + text[-42:]

def requires_operator_decision(path):
    text = read_text(path).lower()
    if "requires operator decision: no" in text or "требует решения оператора: нет" in text:
        return False
    markers = [
        "requires operator decision: yes",
        "требует решения оператора: да",
        "operator decision required",
        "operator_decision_required",
        "disagreement_requires_operator",
        "архитектурное разногласие",
    ]
    return any(m in text for m in markers)

def get_section(text, names):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if low.startswith("## "):
            header = low[3:].strip()
            if any(header.startswith(name) for name in names):
                start = i + 1
                break
    if start is None:
        return ""
    out = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        if line.strip():
            out.append(line.strip())
    return "\n".join(out).strip()

def one_line(text, limit=500):
    value = " ".join([x.strip() for x in text.splitlines() if x.strip()])
    return value[:limit]

def extract_options(text):
    raw = get_section(text, ["варианты", "options", "decision options", "варианты решения"])
    opts = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("---"):
            continue
        s = s.lstrip("- ").strip()
        if s:
            opts.append(s[:180])
    if len(opts) < 2:
        opts = [
            "Подтвердить согласованное решение Claude↔GPT",
            "Вернуть вопрос Claude↔GPT на доработку",
            "Свой вариант оператора",
        ]
    elif len(opts) == 2:
        opts.append("Свой вариант / доработать")
    return opts[:3]

def extract_payload(path):
    text = read_text(path)
    question = get_section(text, ["вопрос", "question", "ключевой вопрос", "что решаем"])
    if not question:
        question = title_from_markdown(path)
    recommendation = get_section(text, ["рекомендация", "recommendation", "позиция gpt", "решение claude", "итог"])
    if not recommendation:
        recommendation = "Рекомендуется выбрать 1, если согласованное решение понятно; выбрать 2, если вопрос или варианты недостаточно ясны."
    return {"question": one_line(question), "options": extract_options(text), "recommendation": one_line(recommendation)}

def option_reason(index, option):
    low = option.lower()
    if "подтверд" in low or "approve" in low or "согласован" in low:
        return "позволяет передать уже согласованный пакет куратору и продолжить внутренний контур."
    if "доработ" in low or "вернуть" in low or "reject" in low:
        return "используется, если вопрос, варианты или обоснование недостаточно ясны для решения."
    if "свой" in low:
        return "оператор может задать другое решение, если предложенные варианты неполные."
    return "вариант предложен в decision package и может быть выбран оператором."

def build_operator_message(path):
    sender, recipient = infer_sender_recipient(path)
    payload = extract_payload(path)
    opts = payload["options"]
    lines = [
        "BEM-MAILBOX | OPERATOR DECISION REQUIRED | workflow_runtime",
        "",
        "Этап: 1/1 (100%)",
        "Дорожная карта: 1/1 (100%)",
        "",
        "Чек-лист:",
        "✅ Claude/GPT обсуждение зафиксировано",
        "✅ Decision package найден",
        "✅ Варианты решения подготовлены",
        "⚠️ Требуется решение оператора",
        "",
        "Вопрос:",
        payload["question"],
        "",
        "Таблица решений:",
        "1) Вариант: " + opts[0],
        "   Обоснование: " + option_reason(1, opts[0]),
        "",
        "2) Вариант: " + opts[1],
        "   Обоснование: " + option_reason(2, opts[1]),
        "",
        "3) Вариант: " + opts[2],
        "   Обоснование: " + option_reason(3, opts[2]),
        "",
        "Рекомендация аудиторов:",
        payload["recommendation"],
        "",
        "Источник:",
        "От: " + sender,
        "Кому: " + recipient,
        "Файл: " + compact_path(path),
        "",
        "Как ответить:",
        "Напиши: 1, 2, 3, да/подтверждаю или свой вариант текстом.",
        "",
        "Что будет после решения:",
        "Пакет решения передаётся куратору, затем во внутренний контур.",
    ]
    return "\n".join(lines)

state = load_state()
processed = set(state.get("processed_files", []))
candidates = []
for d in MAILBOX_DIRS:
    if d.exists():
        candidates.extend(sorted([p for p in d.glob("*.md") if p.is_file()], key=lambda p: str(p)))

picked = None
for path in candidates:
    if str(path) not in processed:
        picked = path
        break

TMP_DIR.mkdir(parents=True, exist_ok=True)
if picked is None:
    pick = {"picked": False, "notify_operator": False, "message": "", "mailbox_file": None, "reason": "no_new_mailbox_file"}
    MSG_PATH.write_text("", encoding="utf-8")
else:
    notify = requires_operator_decision(picked)
    message = build_operator_message(picked) if notify else ""
    reason = "operator_decision_required" if notify else "routine_mailbox_no_telegram"
    pick = {"picked": True, "notify_operator": notify, "message": message, "mailbox_file": str(picked), "reason": reason}
    MSG_PATH.write_text(message, encoding="utf-8")

PICK_PATH.write_text(json.dumps(pick, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"picked": pick["picked"], "notify_operator": pick["notify_operator"], "mailbox_file": pick["mailbox_file"], "reason": pick["reason"]}, ensure_ascii=False))
