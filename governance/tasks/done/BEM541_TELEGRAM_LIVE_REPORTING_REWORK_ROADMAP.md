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


---

## Result
BEM-541 PASS. Provider probe before reserve and Telegram delivery synthetic proof completed.

Evidence:
- BEM-541.1 provider probe: 61fd6f88d355ebea3555388624bfd4bb512e7ade
- BEM-541.2 provider audit: 4636585aeffef45652adecc12228174cb4c4492f
- BEM-541.3 Telegram sender contract: 3fca43fc951b9f8bab8f711c83d55d4797926e5a
- BEM-541.4 Telegram delivery synthetic: 1601c023c42b789a7cdcd6b67b3ec2f73dc483d7
- BEM-541.5 corrected retest: final commit

Blocker: null
