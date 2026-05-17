# BEM-535 | Provider Contours + external cron -> Deno -> workflow_dispatch Telegram Reporting Roadmap

Дата: 2026-05-17 | 13:02 (UTC+3)

## Цель
Доработать внутренний контур с учётом основного и резервного provider-contours, контроля лимитов, переключения Claude -> GPT reserve, обязательной роли analyst на GPT Codex и hourly Telegram canonical reporting через внутренний external cron -> Deno -> workflow_dispatch.

## Архитектурные уточнения
- Curator: GPT Codex / GPT control layer.
- Analyst: GPT Codex.
- Primary provider contour: Claude.
- Reserve provider contour: GPT.
- Provider switching criterion: claude.yml outcome=failure/cancelled or transport result status=failed/timeout/cancelled; provider-adapter then selects GPT reserve.
- Telegram hourly reporting: через внутренний external cron -> Deno -> workflow_dispatch, не через GitHub Actions schedule trigger.
- GitHub schedule triggers остаются запрещены.
- Telegram live token/secrets не хранятся в репозитории.

## Текущее состояние после BEM-531/BEM-533
- BEM-531 закрыт: internal role-based contour PASS.
- BEM-533 закрыт: Telegram branch active_synthetic_verified.
- Main/reserve provider failover E2E ещё не доказан.
- Hourly canonical Telegram report через external cron -> Deno -> workflow_dispatch ещё не доказан.

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

### BEM-535.5 — External cron -> Deno -> workflow_dispatch Telegram hourly report contract
Формализовать hourly canonical report через внутренний external cron -> Deno -> workflow_dispatch: payload по канону, periodicity=1h, destination=Telegram bot, no GitHub schedule.
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
- external cron -> Deno -> workflow_dispatch path documented;
- no GitHub schedule triggers;
- no secrets in files;
- blocker=null.


## Claude review corrections applied
- Claude cannot self-report ChatGPT UI limits through GitHub Actions.
- Real detection mechanism: claude.yml outcome=failure/cancelled OR transport result status=failed/timeout/cancelled.
- Provider adapter reads failed Claude result and routes to GPT reserve.
- Hourly Telegram reporting uses external cron -> Deno endpoint -> workflow_dispatch curator-hourly-report.yml.
- GitHub Actions schedule triggers remain prohibited.


---

## Result
BEM-535 PASS. Provider failover and Telegram hourly reporting architecture verified synthetically.

Evidence:
- BEM-535.1 architecture contract: f1ca30827a7c0c9a2366eeb2d305db26afd5eb63
- BEM-535.2 provider limit state: babcc559ad9a8bbc9f65e24abad1a7b9bdb6e155
- BEM-535.3 provider-adapter failover: 364f8d2295677778efca5f9ad9d37e56f6e32d2b
- BEM-535.4 synthetic failover E2E: c97be7431f4d50a4e77193df86a95570a470ab46
- BEM-535.5 hourly Telegram contract: 1210f0bd094b2688ac9dca747c52201030da6fca
- BEM-535.6 hourly Telegram synthetic payload: 9d73b9f3b88ea571c207d74d37b0a23a38972e84
- BEM-535.7 final status: final commit

Blocker: null
