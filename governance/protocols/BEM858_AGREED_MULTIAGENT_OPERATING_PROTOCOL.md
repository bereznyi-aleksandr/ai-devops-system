# BEM-858 | AGREED MULTIAGENT OPERATING PROTOCOL

Дата: 2026-05-24 | 15:56 (UTC+3)
Версия: v1.0
Источник согласования: governance/audit_mailbox/claude_to_gpt/bem857_claude_direct_response.md
Статус: AGREED_WITH_LIMITATION

## Решение

| Пункт | Согласованное правило | Статус | Обоснование |
|---|---|---|---|
| 1 | GPT и Claude работают как peer-аудиторы | APPROVED | Claude BEM-857 approved peer-модель |
| 2 | Старший субъект — только оператор | APPROVED | Claude BEM-857 approved |
| 3 | Audit mailbox остаётся основным repo-native каналом | APPROVED | Claude BEM-857 approved |
| 4 | Telegram используется как gate для финальных решений оператора, не как транспорт содержимого между агентами | APPROVED | Claude BEM-857 approved |
| 5 | Handoff после решения идёт только в Curator | APPROVED | Claude BEM-857 approved |
| 6 | Передача решений напрямую Analyst/Executor запрещена | APPROVED | Claude BEM-857 approved |
| 7 | Curator = GPT/Codex, Analyst = GPT/Codex сохраняются как решения оператора | APPROVED | Claude BEM-857 approved |
| 8 | Следующий шаг — развивать mailbox dispatcher | APPROVED | Claude BEM-857 approved |
| 9 | Технические разногласия GPT и Claude решают сами | CHANGE_REQUIRED_ACCEPTED | Правка Claude BEM-857 принята |
| 10 | Архитектурные разногласия выносятся оператору через Telegram | CHANGE_REQUIRED_ACCEPTED | Правка Claude BEM-857 принята |
| 11 | Разногласие с решением оператора запрещено | CHANGE_REQUIRED_ACCEPTED | Правка Claude BEM-857 принята |

## Каналы связи

| Канал | Текущий статус | Использование | Ограничение |
|---|---|---|---|
| Claude direct GitHub MCP → claude_to_gpt | WORKING | Основной рабочий канал Claude на текущем этапе | Не является GitHub Actions Claude Code Action |
| claude-code-action@v1 через GitHub Actions | NOT_PROVEN | Только после отдельного smoke-test | Требует валидный CLAUDE_CODE_OAUTH_TOKEN или ANTHROPIC_API_KEY |
| Telegram | OPERATOR_NOTIFICATION_ONLY | Уведомления и финальные gates | Не использовать как relay для содержимого Claude↔GPT |

## PASS criteria

| Критерий | Требование | Статус на момент протокола |
|---|---|---|
| Реальный ответ Claude | Файл начинается с CLAUDE RESPONSE и содержит DECISION | PASS через BEM-857 |
| Runtime state Claude Action | latest.outcome != failure | NOT_PROVEN |
| Dispatch result | workflow_dispatch_results имеет актуальный status | PARTIAL |

## Итог

Согласованный рабочий протокол принят: GPT и Claude продолжают как peer-аудиторы через repo-native mailbox. До восстановления Claude Code Action рабочим каналом Claude считается прямой GitHub MCP-коммит в `governance/audit_mailbox/claude_to_gpt/`.

No issue comments.
