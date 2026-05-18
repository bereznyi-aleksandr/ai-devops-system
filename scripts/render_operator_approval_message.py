#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
KYIV = timezone(timedelta(hours=3))
INP = Path("governance/operator_decisions/pending/current_decision.json")
OUT = Path("governance/tmp/operator_approval_message.txt")
def load():
    if not INP.exists():
        return {"question":"Нет активного вопроса для согласования.","options":[]}
    try:
        return json.loads(INP.read_text(encoding="utf-8", errors="ignore"))
    except:
        return {"question":"Ошибка чтения пакета согласования.","options":[]}
def row(n, name, reason):
    name = str(name)[:24]
    reason = str(reason)[:44]
    return f"{n:<2} | {name:<24} | {reason}"
data=load()
now=datetime.now(KYIV)
question=str(data.get("question") or data.get("title") or "Вопрос не указан")
options=data.get("options") or []
lines=[]
lines.append("BEM-APPROVAL | OPERATOR DECISION REQUIRED")
lines.append("Дата: " + now.strftime("%Y-%m-%d | %H:%M (UTC+3)"))
lines.append("")
lines.append("Вопрос:")
lines.append(question)
lines.append("")
lines.append("```")
lines.append("№  | Наименование варианта   | Обоснование")
lines.append("---+--------------------------+---------------------------------------------")
if options:
    for idx,opt in enumerate(options,1):
        lines.append(row(idx, opt.get("name") or opt.get("title") or opt.get("variant") or ("Вариант " + str(idx)), opt.get("reason") or opt.get("rationale") or opt.get("justification") or "Обоснование не указано"))
else:
    lines.append(row(1, "Подтвердить", "Разрешить выполнение предложенного решения"))
    lines.append(row(2, "Вернуть", "Нужна доработка вопроса или вариантов"))
    lines.append(row(3, "Свой вариант", "Оператор пишет решение текстом"))
lines.append("```")
lines.append("")
lines.append("Как ответить: напишите номер варианта или свой текст.")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(SEP.join(lines)+SEP, encoding="utf-8")
print(str(OUT))
