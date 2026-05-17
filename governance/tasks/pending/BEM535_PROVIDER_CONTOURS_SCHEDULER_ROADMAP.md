# BEM-535 | Provider Contours + GPT Scheduler Telegram Reporting Roadmap

Дата: 2026-05-17 | 13:02 (UTC+3)

## Цель
Доработать внутренний контур с учётом основного и резервного provider-contours, контроля лимитов, переключения Claude -> GPT reserve, обязательной роли analyst на GPT Codex и hourly Telegram canonical reporting через внутренний GPT Scheduler.

## Архитектурные уточнения
- Curator: GPT Codex / GPT control layer.
- Analyst: GPT Codex.
- Primary provider contour: Claude.
- Reserve provider contour: GPT.
- Provider switching criterion: Claude unavailable, limit_exceeded, quota_exceeded, timeout, provider_failed.
- Telegram hourly reporting: через внутренний GPT Scheduler, не через GitHub Actions schedule trigger.
- GitHub schedule triggers остаются запрещены.
- Telegram live token/secrets не хранятся в репозитории.

## Текущее состояние после BEM-531/BEM-533
- BEM-531 закрыт: internal role-based contour PASS.
- BEM-533 закрыт: Telegram branch active_synthetic_verified.
- Main/reserve provider failover E2E ещё не доказан.
- Hourly canonical Telegram report через GPT Scheduler ещё не доказан.

## Этапы BEM-535

### BEM-535.1 — Provider contour architecture contract
Формализовать схему: primary Claude contour, reserve GPT contour, Curator=GPT Codex, Analyst=GPT Codex, Auditor/Executor routing, лимиты и причины переключения.
PASS: protocol file, schema, sample provider status records.

### BEM-535.2 — Provider limit state + decision matrix
Создать/обновить state для provider limits: claude.status, claude.limit_state, gpt_reserve.status, last_switch_reason, switch_history.
PASS: governance/state/provider_contour_state.json + report.

### BEM-535.3 — Provider adapter failover implementation
Доработать provider-adapter contract/workflow/file-protocol: при Claude limit_exceeded/unavailable автоматически выбирать GPT reserve.
PASS: adapter audit/patch, no secrets, no paid API default, no schedule.

### BEM-535.4 — Synthetic failover E2E
Провести два synthetic теста: primary Claude available -> Claude selected; Claude limit_exceeded -> GPT reserve selected.
PASS: transport records, provider state, report, blocker=null.

### BEM-535.5 — GPT Scheduler hourly Telegram report contract
Формализовать hourly canonical report через внутренний GPT Scheduler: payload по канону, periodicity=1h, destination=Telegram bot, no GitHub schedule.
PASS: protocol, sample hourly report payload, scheduler state fields.

### BEM-535.6 — Telegram hourly reporting synthetic test
Провести synthetic generation canonical report payload для Telegram без live token: статус контуров, last SHA, blocker, next action.
PASS: sample payload, transport record, contour_status update.

### BEM-535.7 — Final contour status update
Обновить contour_status.json: provider_failover=verified, telegram_hourly_report=synthetic_verified, current provider state, blocker=null.
PASS: done-marker, PASS report, status update.

## PASS всей BEM-535
- provider_contour_state.json exists;
- Claude primary / GPT reserve failover synthetic E2E PASS;
- Curator and Analyst roles explicitly mapped to GPT Codex;
- Telegram hourly canonical report contract exists;
- GPT Scheduler path documented;
- no GitHub schedule triggers;
- no secrets in files;
- blocker=null.
