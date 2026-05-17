#!/usr/bin/env python3
import json
from pathlib import Path

MAILBOX_DIRS = [
    Path("governance/audit_mailbox/claude_to_gpt"),
    Path("governance/audit_mailbox/gpt_to_claude"),
]
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

def title_from_markdown(path):
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                return line[2:].strip()[:96]
    except Exception:
        pass
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
    if len(text) <= 90:
        return text
    return text[:42] + "…" + text[-42:]

def operator_action_for(recipient):
    if recipient == "GPT" or recipient == "Claude":
        return "Не требуется. Это уведомление о синхронизации Claude↔GPT."
    return "Проверить mailbox routing."

def recipient_action_for(recipient):
    if recipient == "GPT":
        return "GPT должен прочитать файл и ответить через mailbox."
    if recipient == "Claude":
        return "Claude должен прочитать файл и ответить через mailbox."
    return "Адресат должен обработать файл mailbox."

def build_message(path):
    sender, recipient = infer_sender_recipient(path)
    title = title_from_markdown(path)
    short_path = compact_path(path)
    lines = [
        "BEM-MAILBOX | УВЕДОМЛЕНИЕ ОПЕРАТОРУ | workflow_runtime",
        "",
        "Этап: 1/1 (100%)",
        "Дорожная карта: 1/1 (100%)",
        "",
        "Чек-лист:",
        "✅ Новое сообщение mailbox обнаружено",
        f"✅ Адресат: {recipient}",
        "✅ Записано в repo mailbox",
        "✅ Действие оператора не требуется",
        "",
        "Сообщение:",
        f"От: {sender}",
        f"Кому: {recipient}",
        f"Тема: {title}",
        f"Файл: {short_path}",
        "",
        f"Действие {recipient}:",
        recipient_action_for(recipient),
        "",
        "Действие оператора:",
        operator_action_for(recipient),
        "",
        "Причина:",
        "Telegram здесь только уведомляет оператора, а не передаёт задачу вручную.",
    ]
    return "\n".join(lines)

state = load_state()
seen = set(state.get("sent_files", []))
candidates = []
for d in MAILBOX_DIRS:
    if d.exists():
        candidates.extend(sorted([p for p in d.glob("*.md") if p.is_file()], key=lambda p: str(p)))
picked = None
for path in candidates:
    if str(path) not in seen:
        picked = path
        break
TMP_DIR.mkdir(parents=True, exist_ok=True)
if picked is None:
    pick = {"picked": False, "message": "", "mailbox_file": None}
    MSG_PATH.write_text("", encoding="utf-8")
else:
    message = build_message(picked)
    pick = {"picked": True, "message": message, "mailbox_file": str(picked)}
    MSG_PATH.write_text(message, encoding="utf-8")
PICK_PATH.write_text(json.dumps(pick, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"picked": pick["picked"], "mailbox_file": pick["mailbox_file"]}, ensure_ascii=False))
