# Telegram input handler contract

Назначение: преобразовать Telegram payload в telegram_input_envelope.

Contract:
- Принимать payload от существующего Telegram/Deno webhook.
- Создавать trace_id/correlation_id.
- Классифицировать command: task, status, report, gate, approve, reject, help.
- По умолчанию маршрутизировать target_curator=EL-CUR-GD-001.
- Не исполнять задачу самостоятельно.
- Возвращать receipt operator-facing каналу.
