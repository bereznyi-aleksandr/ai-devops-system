# BEM-695 | Fix Hourly Snapshot Commit | PASS

Дата: 2026-05-19 | 10:05 (UTC+3)

Root cause: snapshot сравнения не был гарантированно добавлен в commit workflow. Без сохранённого snapshot следующий hourly запуск снова отправлял полную таблицу.

Blocker: null
