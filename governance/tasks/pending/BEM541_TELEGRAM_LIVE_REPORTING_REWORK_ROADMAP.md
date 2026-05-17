# BEM-541 | Provider Probe + Telegram Delivery Rework Roadmap

Дата: 2026-05-17 | 14:09 (UTC+3)

## Причина
BEM-540 подтвердил synthetic/system scope, но оператор указал на реальный gap: перед переключением на GPT reserve нужно сначала проверить Claude. Также Telegram проверен только до outbox, без delivery proof.

## Roadmap

### BEM-541.1 — Provider live probe before reserve
Перед failover добавлять provider probe: проверить актуальный Claude status/outcome/last transport result. Если Claude active — не переключать на GPT reserve.
PASS: provider probe protocol + state fields + synthetic tests: Claude active -> Claude selected; Claude failed -> GPT reserve.

### BEM-541.2 — Provider selection audit record
Каждый выбор провайдера писать в `governance/transport/results.jsonl` как `provider_selection_decision` с reason, evidence_path, source_record.
PASS: records exist, no silent switch.

### BEM-541.3 — Telegram sender/delivery contract
Доработать Telegram: outbox -> sender -> delivery status. Описать runtime secret requirements, retry, delivery_result records, no token in files.
PASS: contract + sample delivery_result records.

### BEM-541.4 — Telegram delivery synthetic E2E
Проверить outbox consumer/sender synthetic: queued_for_sender -> sent_synthetic / failed_synthetic with retry fields.
PASS: telegram_outbox read, delivery result appended to transport, state updated.

### BEM-541.5 — Corrected full system retest
Повторить системный тест: provider probe first, curator cycle, provider decision, Telegram delivery result.
PASS: no forced GPT reserve when Claude active; explicit provider decision records; Telegram delivery result exists.
