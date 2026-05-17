# BEM-535.1 | Provider Contour Failover Contract

Дата: 2026-05-17 | 13:05 (UTC+3)

## Цель
Формализовать основной и резервный контуры провайдеров внутреннего контура разработки.

## Контуры
- Primary provider contour: Claude.
- Reserve provider contour: GPT.
- Curator: GPT Codex / GPT control layer.
- Analyst: GPT Codex.

## Реальный механизм обнаружения лимита Claude
Claude не может сам сообщить GitHub Actions, что у него закончились UI-лимиты. Поэтому система НЕ полагается на самосообщение Claude.

Рабочие сигналы недоступности Claude:
1. `claude.yml` завершился с `outcome=failure`.
2. `claude.yml` завершился с `outcome=cancelled`.
3. В `governance/transport/results.jsonl` появилась запись Claude со `status=failed`.
4. В transport появилась запись Claude со `status=timeout` или `status=cancelled`.
5. Истёк TTL ожидания ответа Claude, и curator/provider-adapter пишет `provider_timeout`.

## Правило failover
Если Claude primary вернул failed/cancelled/timeout или не дал результата в TTL, provider-adapter выбирает GPT reserve и пишет решение в transport/state.

## Decision matrix
| Claude signal | Decision | Обоснование |
|---|---|---|
| completed | use claude_primary | Primary provider successful |
| failed | switch_to_gpt_reserve | Claude path unavailable or limit/error hit |
| cancelled | switch_to_gpt_reserve | Claude path interrupted |
| timeout | switch_to_gpt_reserve | No response inside TTL |
| missing_result_after_ttl | switch_to_gpt_reserve | No reliable Claude output |

## Hourly Telegram reporting mechanism
Custom GPT не запускается сам по расписанию. GitHub Actions `schedule` запрещён.

Разрешённый путь:
`external cron service -> Deno endpoint -> workflow_dispatch curator-hourly-report.yml -> Telegram bot send`.

Это не GitHub Actions schedule trigger. Секреты Telegram не хранятся в файлах репозитория.

## Запреты
- No GitHub Actions schedule triggers.
- No issue #31 comments.
- No secrets in files.
- No paid OpenAI API by default.
