# BEM-531 | Report for Claude: Internal Contour Roadmap Update

Дата: 2026-05-17 | 12:50 (UTC+3)

## Причина обновления
Оператор уточнил, что первым этапом roadmap внутреннего контура должна быть очистка репозитория от мусора: устаревших файлов, failed/superseded artifacts, stale pending records и исторических blocker-файлов. Очистка должна выполняться без нарушения внешнего GPT autonomy contour и внутреннего role-based contour.

## Что изменено
- В `governance/tasks/pending/BEM531_INTERNAL_ROLE_CONTOUR_ROADMAP.md` добавлен первый этап `BEM-531.00 — Repository archive cleanup preflight`.
- Curator intake переименован в `BEM-531.01 — Unified curator intake architecture`.
- Общее количество этапов BEM-531 обновлено до 8.

## Новая последовательность
1. BEM-531.00 Repository archive cleanup preflight.
2. BEM-531.01 Unified curator intake architecture.
3. BEM-531.1 Role state schema audit and normalization.
4. BEM-531.2 File transport contract.
5. BEM-531.3 Role orchestrator workflow audit.
6. BEM-531.4 Provider adapter workflow audit.
7. BEM-531.5 Synthetic role cycle E2E.
8. BEM-531.6 Internal contour dashboard.

## Требования к cleanup
- Ничего не удалять без архива.
- Всё переносить в `governance/archive` с manifest.
- Не трогать активные workflows/state/transport/protocols без точного основания.
- Не нарушать Deno, codex-runner, Python executor v3.
- Не нарушать curator/analyst/auditor/executor chain.
- No issue #31 comments.
- No schedule triggers.
- No paid OpenAI API.

## Важное замечание
Ранее уже был выполнен BEM-532 Phase 1 archive cleanup. Для BEM-531.00 требуется не повторять слепую очистку, а провести полноценный preflight/inventory и использовать BEM-532 Phase 1 как уже выполненный historical cleanup input.

## Blocker
null
