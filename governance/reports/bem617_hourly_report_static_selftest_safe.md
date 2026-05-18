# BEM-617 | Hourly Report Static Selftest Safe | FAILED

Дата: 2026-05-18 | 06:49 (UTC+3)

## Checks

- renderer_exists: PASS
- recorder_exists: PASS
- workflow_exists: PASS
- renderer_syntax_compile: FAIL
- recorder_syntax_compile: FAIL
- renderer_source_contains_BEM-HOURLY: PASS
- renderer_source_contains_Этап:: PASS
- renderer_source_contains_Дорожная карта:: PASS
- renderer_source_contains_Чек-лист:: PASS
- renderer_source_contains_Мониторинг:: PASS
- renderer_source_contains_Provider route: PASS
- renderer_source_contains_Основной контур: PASS
- renderer_source_contains_Резервный контур: PASS
- renderer_source_contains_Telegram delivery: PASS
- renderer_source_contains_Blocker: PASS
- renderer_source_contains_Следующее действие: PASS
- workflow_has_allowed_schedule: PASS
- workflow_no_inline_python_heredoc: PASS
- workflow_uses_renderer_and_recorder: PASS
- workflow_commit_conflict_safe: PASS
- recorder_updates_delivery: PASS
- schedule_only_curator_hourly: FAIL
- sample_no_wide_pipe_table: PASS

## Sample preview
```text
BEM-HOURLY | SYSTEM MONITORING REPORT | workflow_runtime

Этап: 4/6 (67%)
Дорожная карта: 4/6 (67%)

Чек-лист:
✅ Роли/контуры проверены
✅ Provider gate выполнен: true
✅ Последние события собраны: 5
✅ Telegram delivery проверяется этим workflow
✅ Blocker: null

Мониторинг:
• Текущий этап
  Описание: canonical_renderer_implemented
  Обоснование: Показывает, на каком участке roadmap находится система.
• Provider route
  Описание: selected=gpt_reserve; reserve_used=true
  Обоснование: Если Claude primary не доказан, система фиксирует fallback.
• Основной контур
  Описание: Claude Code primary = not selected or not proven
  Обоснование: Отчёт явно показывает, сработал ли основной provider.
• Резервный контур
  Описание: GPT reserve = used
  Обоснование: Fallback фиксируется без имитации PASS.
• Следующее действие
  Описание: finish BEM-605 execution, selftest, monitoring report
  Обоснование: Roadmap продолжается без ожидания отчёта.

```

## Blocker
{
  "code": "HOURLY_REPORT_STATIC_SELFTEST_FAILED",
  "failed": [
    {
      "name": "renderer_syntax_compile",
      "pass": false,
      "error": "syntax_compile_failed"
    },
    {
      "name": "recorder_syntax_compile",
      "pass": false,
      "error": "syntax_compile_failed"
    },
    {
      "name": "schedule_only_curator_hourly",
      "pass": false,
      "schedule_files": [
        ".github/workflows/curator-hourly-report.yml",
        ".github/workflows/telegram-outbox-dispatch.yml"
      ]
    }
  ]
}
