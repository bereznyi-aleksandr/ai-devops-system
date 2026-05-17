# BEM-532 | Repository Archive Cleanup Roadmap

Дата: 2026-05-17 | 12:47 (UTC+3)

## Цель
Очистить репозиторий от устаревших файлов и записей внешнего и внутреннего контуров, не удаляя исторические доказательства: всё переносится в governance/archive.

## Этапы
1. Phase 1 — conservative archive cleanup: failed/superseded external-contour artifacts and stale pending tasks.
2. Phase 2 — documentation reference cleanup: убрать ссылки на устаревшие Codex CLI/OpenAI API пути из активных документов, если они не являются историей.
3. Phase 3 — internal contour preflight cleanup: перед BEM-531 удалить/архивировать устаревшие записи transport/state, не входящие в текущую curator-first архитектуру.
4. Phase 4 — final cleanliness audit: inventory active vs archive, no stale pending, no obsolete blockers, no schedule, no issue #31.

## Правило
Ничего не удалять без архива. Активные state/workflow/protocol/report files не трогать без точного основания.
