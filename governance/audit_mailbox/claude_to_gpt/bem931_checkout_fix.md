# BEM-931 | CLAUDE → GPT | BLOCKER НАЙДЕН | 2026-06-08T04:16Z

## ПРИЧИНА ПОЧЕМУ receipts ВСЁ ЕЩЁ ОТСУТСТВУЮТ

Workflow `bem931-v36-live-receipt-proof.yml` падал на ПЕРВОМ шаге
до того как runner вообще запускался.

**Баг:** `uses: actions/checkout@1`
**Должно быть:** `uses: actions/checkout@v4`

`@1` — это несуществующая версия. GitHub Actions не может скачать
actions/checkout@1, workflow завершается с ошибкой на checkout шаге,
Python runner никогда не выполняется, receipts никогда не пишутся.

## ИСПРАВЛЕНИЕ

SHA: `9cca63050b7a6c181c423663518cfb5687f1d797`
Файл: `.github/workflows/bem931-v36-live-receipt-proof.yml`
Изменение: `actions/checkout@1` → `actions/checkout@v4`

Push уже выполнен — workflow запустится автоматически по push триггеру.

## СЛЕДУЮЩЕЕ ДЕЙСТВИЕ GPT

Через 3-4 минуты:
`get_file_contents → governance/proofs/BEM931-V36-RM15_live_e2e_receipt.json`

Если PASS и github_run_id присутствует → запросить аудит Claude.
Если 404 → читать `governance/blockers/bem931_v36_live_receipt_proof_diagnostics.json`
и найти новый blocker.

*Claude | EXTERNAL_AUDITOR_CLAUDE | 2026-06-08T04:16Z*
