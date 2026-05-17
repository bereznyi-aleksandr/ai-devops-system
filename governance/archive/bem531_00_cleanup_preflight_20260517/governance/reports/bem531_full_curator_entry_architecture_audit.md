# BEM-531 | Full Curator Entry Architecture Audit

Дата: 2026-05-17 | 12:42 (UTC+3)

## Вывод
Да, полная целевая структура должна рассматриваться как несколько внешних веток с единой точкой входа через curator. Предыдущий audit учёл curator как роль, но недостаточно явно учёл Telegram bot/webhook как отдельную внешнюю ветку.

## Статус
MAPPED

## Проверенные файлы
- governance/INTERNAL_CONTOUR_REFERENCE.md: exists, bytes=7525
- governance/GPT_HANDOFF.md: exists, bytes=4039
- governance/GPT_WRITE_CHANNEL.md: exists, bytes=5653
- governance/state/role_cycle_state.json: exists, bytes=273
- governance/transport/results.jsonl: exists, bytes=0
- governance/protocols/HANDOFF_PROTOCOL_CLAUDE_GPT.md: exists, bytes=39
- governance/protocols/PRODUCTION_STABILITY_RUNBOOK.md: exists, bytes=1304
- governance/protocols/MONITORING_ALERTS_RUNBOOK.md: exists, bytes=1221
- .github/workflows/role-orchestrator.yml: exists, bytes=6188
- .github/workflows/provider-adapter.yml: exists, bytes=12136
- .github/workflows/codex-runner.yml: exists, bytes=23895

## Проверка веток и ролей
```json
{
  "gpt_external_auditor": true,
  "claude_external_auditor": true,
  "telegram_bot_or_webhook": true,
  "curator_role": true,
  "analyst_role": true,
  "auditor_role": true,
  "executor_role": true,
  "file_transport": true,
  "role_orchestrator": true,
  "provider_adapter": true
}
```

## Целевая модель
# Full architecture model

External inputs:
1. GPT external auditor / autonomous agent.
2. Claude external auditor / direct patch agent.
3. Telegram bot / webhook user-facing branch.

Single entry point:
- Curator receives or normalizes external input, performs intake and triage, opens or updates role-cycle state, selects next internal role, controls handoff and closure.

Internal contour:
- Curator -> Analyst -> Auditor -> Executor -> Auditor final check -> Curator closure.

Execution layer:
- GitHub Actions workflows, provider adapter, file transport, Python executor v3.

State and transport:
- role_cycle_state.json stores current cycle and next role.
- governance/transport/results.jsonl stores file-based exchange/results.


## Текущее понимание состояния
- Внешний GPT contour уже автономен и может писать в repo через Deno + GitHub Actions + Python executor v3.
- Claude branch используется для сложных direct patches и внешнего аудита.
- Telegram/webhook branch присутствует на уровне сервиса Deno webhook и должна входить в тот же curator intake, а не идти параллельно внутреннему контуру.
- Внутренний контур ещё требует формализации curator intake schema, role state schema, transport schema и synthetic E2E на всех ветках входа.

## Что надо добавить в roadmap
1. BEM-531.00 Unified curator intake architecture.
2. Curator intake schema для GPT, Claude и Telegram.
3. Transport samples для каждой внешней ветки.
4. E2E: Telegram/GPT/Claude input -> curator -> analyst -> auditor -> executor -> curator closure.

## Gaps
null

## Blocker
null для аудита. Полный PASS внутреннего контура возможен только после выполнения BEM-531 roadmap с учётом curator и Telegram branch.
