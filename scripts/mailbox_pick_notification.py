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
            return line[2:].strip()[:96]
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
    markers = [
        "requires operator decision: yes",
        "требует решения оператора: да",
        "operator decision required",
        "operator_decision_required",
        "disagreement_requires_operator",
        "архитектурное разногласие",
    ]
    return any(marker in text for marker in markers)

def build_operator_message(path):
    sender, recipient = infer_sender_recipient(path)
    title = title_from_markdown(path)
    short_path = compact_path(path)
    lines = [
        "BEM-MAILBOX | OPERATOR DECISION REQUIRED | workflow_runtime",
        "",
        "Этап: 1/1 (100%)",
        "Дорожная карта: 1/1 (100%)",
        "",
        "Чек-лист:",
        "✅ Claude↔GPT обсуждение зафиксировано",
        "✅ Требуется решение оператора",
        "✅ Решение будет передано куратору",
        "",
        "Вопрос:",
        f"От: {sender}",
        f"Кому: {recipient}",
        f"Тема: {title}",
        f"Файл: {short_path}",
        "",
        "Действие оператора:",
        "Принять финальное решение по согласованному/спорному вопросу.",
        "",
        "После решения:",
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
