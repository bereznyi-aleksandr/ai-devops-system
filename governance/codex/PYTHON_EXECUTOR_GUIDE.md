# Python Executor — Руководство

**BEM-525** | Версия: 2.0 | 2026-05-17

---

## Что это

Python executor — бесплатный исполнитель задач в GitHub Actions (ubuntu-latest).
Запускается через Deno канал: `createCodexTask` → `codex-runner.yml`.

Не требует: Codex CLI, OPENAI_API_KEY, self-hosted runner, платных API.

---

## Поддерживаемые операции

### 1. Создать файл

```
Create file <path> with content <text>
```

Пример objective:
```
Create file governance/reports/test.md with content '# Test report. Created by GPT agent.'
No issue comments.
```

---

### 2. Удалить файл

```
Delete file <path>
```

> Git не умеет физически удалять файлы через скрипт без commit --remove.
> Вместо удаления файл заменяется archived-маркером.
> Если нужно реальное удаление — Claude делает это напрямую через MCP.

Пример:
```
Delete file governance/tasks/pending/OLD_TASK.md
No issue comments.
```

---

### 3. Переместить файл

```
Move file <path> to <path2>
```

Копирует содержимое в новый путь, оригинал заменяет archived-маркером.

Пример:
```
Move file governance/tasks/pending/TASK.md to governance/tasks/done/TASK.md
No issue comments.
```

---

### 4. Дописать в файл

```
Append to <path>: <content>
```

Добавляет строку в конец файла. Работает для `.jsonl`, `.md`, `.txt`.

Пример:
```
Append to governance/events/gpt_dev_runner.jsonl: {"event":"test","trace":"bem525","at":"2026-05-17"}
No issue comments.
```

---

### 5. Обновить одно поле JSON

```
Set <path> field <key>=<value>
```

Читает JSON файл, обновляет поле, сохраняет. Автоматически добавляет `updated_at`.

Поддерживаемые типы значений: `true/false`, числа, строки.

Пример:
```
Set governance/state/role_cycle_state.json field status=completed
No issue comments.
```

---

### 6. Обновить несколько полей JSON

```
Set <path> fields: <key1>=<val1>, <key2>=<val2>
```

Пример:
```
Set governance/state/role_cycle_state.json fields: status=completed, current_role=null
No issue comments.
```

---

## Комбинирование операций

Можно выполнить несколько операций в одном objective:

```
Create file governance/tasks/done/BEM525.md with content '# BEM-525 done'.
Move file governance/tasks/pending/BEM525.md to governance/tasks/archive/BEM525.md.
Set governance/state/roadmap_state.json field updated_at=2026-05-17T06:00:00Z.
No issue comments.
```

---

## Ограничения

| Операция | Ограничение |
|---|---|
| Delete | Заменяет archived-маркером, не удаляет физически |
| Произвольный код | Не поддерживается — только паттерны выше |
| Сложная логика | Не поддерживается — Claude делает напрямую |
| Бинарные файлы | Не поддерживается |

**Для сложных задач** (рефакторинг кода, анализ, удаление файлов) — передать Claude.

---

## Как запустить через GPT

```
createCodexTask(
  trace_id  = "уникальный_id",
  task_type = "code_patch",
  title     = "короткое название",
  objective = "<паттерн из списка выше>. No issue comments."
)
```

Затем:
```
getCodexStatus(trace_id="тот же id")
```

---

## Как запустить напрямую (GitHub Actions)

```
GitHub → Actions → Codex Runner → Run workflow
  trace_id: <id>
  task_path: (оставить пустым)
```

---

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `changed_files` только proof | objective не совпал ни с одним паттерном | Проверить формат паттерна — точное совпадение важно |
| `status=blocked, TASK_FILE_NOT_FOUND` | task file не создан | Проверить что `createCodexTask` вернул `ok=true` |
| `status=failed` | Ошибка при выполнении | Читать `blocker.message` — там точная ошибка |

---

*BEM-525 | 2026-05-17 | Claude Sonnet 4.6*
