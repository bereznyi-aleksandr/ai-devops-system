#!/usr/bin/env python3
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
OUT = Path("governance/tmp/telegram_send_smoke_message.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("BEM-664 | TELEGRAM DELIVERY SMOKE | workflow_runtime" + SEP + SEP + "Проверка доставки Telegram из GitHub Actions. Если это сообщение получено, bot/chat secrets and sendMessage path work." + SEP, encoding="utf-8")
print(str(OUT))
