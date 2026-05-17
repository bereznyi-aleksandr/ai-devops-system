# BEM-531 | Claude Review Applied to Internal Contour Roadmap

Дата: 2026-05-17 | 12:45 (UTC+3)

## Что принято из замечаний Claude

| Наименование | Описание | Обоснование |
|---|---|---|
| Cleanup first | Cleanup preflight оставлен первым этапом | Перед разработкой нельзя строить контур на грязной базе |
| Curator intake | Curator остаётся единой точкой входа | Ключевой принцип архитектуры |
| Agent lifecycle | В state schema добавлен lifecycle CANDIDATE -> ACTIVE -> RETIRED | Нужно управлять сбоями и заменой агентов |
| Failure handling | Transport contract включает role_timeout, role_failed, validation_failed, executor_failed | Нужен не только happy path |
| Workflow audit combined | Orchestrator и provider adapter объединены в один этап | Дешевле и проще, оба относятся к workflow audit |
| E2E two-level | Minimal E2E и full E2E объединены в один этап с двумя подзадачами | Даёт 7 этапов без потери проверки |
| Dashboard simplified | UI/dashboard заменён на governance/state/contour_status.json | Дешевле, проще, машинно читается GPT |
| Telegram scope | Telegram branch признан частью общей архитектуры, но исключён из BEM-531 scope и отложен | Снижает сложность текущей разработки |

## Итоговая roadmap
7 этапов: cleanup, curator intake, role state + lifecycle, transport + failure handling, workflow audit, synthetic E2E two-level, contour_status.json.

## Blocker
null
