# GPT WRITE CHANNEL — ai-devops-system

**BEM-525** | Версия: 2.0 | 2026-05-17

---

## Единственный автономный путь записи

```
GPT открывает URL → Deno принимает задачу → GitHub Actions пишет в репо
```

MCP write-actions (create_file, update_file, create_commit) — confirm-gate в ChatGPT → нарушение автономности. Не использовать.

---

## Алгоритм

```
1. createCodexTask(
     trace_id  = "уникальный_id",
     task_type = "code_patch",
     title     = "название",
     objective = "<паттерн из списка ниже>. No issue comments."
   )

2. ok=true + dispatch=204 → ждать 1-3 минуты

3. getCodexStatus(trace_id="тот же id")
   completed → fetch_file результат
   blocked   → читать blocker.code
   queued    → ждать 2 мин, повторить один раз

4. Если два раза queued — остановиться, зафиксировать blocker.
   Не полить getCodexStatus бесконечно.
```

---

## Поддерживаемые паттерны (Python executor v2)

### Создать файл
```
Create file <path> with content <text>
```

### Удалить файл (archived-маркер)
```
Delete file <path>
```

### Переместить файл
```
Move file <path> to <path2>
```

### Дописать в файл
```
Append to <path>: <content>
```

### Обновить поле JSON
```
Set <path> field <key>=<value>
```

### Обновить несколько полей JSON
```
Set <path> fields: <key1>=<val1>, <key2>=<val2>
```

### Комбинация операций
```
Create file governance/tasks/done/TASK.md with content '# Done'.
Delete file governance/tasks/pending/TASK.md.
Set governance/state/roadmap_state.json field updated_at=2026-05-17T06:00:00Z.
No issue comments.
```

---

## Ограничения Python executor

| Не умеет | Альтернатива |
|---|---|
| Физически удалять файлы | Заменяет archived-маркером |
| Произвольный код | Claude делает напрямую через MCP |
| Сложный рефакторинг | Claude делает напрямую через MCP |
| Бинарные файлы | Не поддерживается |

**Полное руководство:** `governance/codex/PYTHON_EXECUTOR_GUIDE.md`

---

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `changed_files` только proof | Паттерн не совпал | Проверить формат — точное совпадение |
| `ok=false, invalid_trace_id` | trace_id содержит спецсимволы | Только `[a-zA-Z0-9_]` до 60 символов |
| `ok=false, session_active` | Активная сессия | Ждать или новый trace_id |
| `ok=false, rate_limited` | Слишком частые запросы | Ждать 60 секунд |
| `status=queued` 5+ мин | Runner не запустился | Проверить GitHub Actions |
| `status=blocked, TASK_FILE_NOT_FOUND` | createCodexTask не создал файл | Проверить `ok=true` в ответе |

---

*BEM-525 | 2026-05-17 | v2.0*
