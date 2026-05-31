# Managed channel consumer contract

Назначение: читать managed channel и маршрутизировать сообщения внутри управляющего контура.

Contract:
- Читать managed_channel_messages.jsonl.
- Поддерживать vertical curator-to-curator routes.
- Поддерживать horizontal Auditor A -> Analyst B verified data transfer.
- Поддерживать horizontal Analyst B -> Auditor A verified data request.
- Записывать event_log_ref и processed_message_id.
- Помещать invalid messages в dead-letter.
