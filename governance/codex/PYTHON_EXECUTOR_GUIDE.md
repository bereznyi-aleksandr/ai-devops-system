# Python Executor v3 — Полное руководство

**BEM-526** | Версия: 3.0 | 2026-05-17

---

## Что это и зачем

Python executor — инструмент GPT-агента для автономного выполнения задач в репозитории.

**GPT думает. Executor делает.**

GPT анализирует задачу, формулирует objective на понятном языке, отправляет через Deno. Executor выполняет операции с файлами и делает коммит. Никакого платного API. Никакого self-hosted runner.

---

## Два уровня работы

### Уровень 1 — Паттерны (12 операций)

Простые операции с файлами. GPT указывает паттерн в objective.

### Уровень 2 — Произвольный Python скрипт

GPT пишет любой Python-код прямо в objective. Executor запускает его. Покрывает 100% задач.

---

## Уровень 1 — Все паттерны

### 1. Создать файл

```
Create file <path> with content <text>
```

Пример:
```
Create file governance/reports/bem526_report.md with content '# BEM-526 отчёт выполнен.'
No issue comments.
```

---

### 2. Удалить файл

```
Delete file <path>
```

> Файл заменяется archived-маркером (git не удаляет физически через скрипт).
> Если нужно полное удаление — использовать Run script (уровень 2).

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
Move file governance/tasks/pending/TASK_123.md to governance/tasks/done/TASK_123.md
No issue comments.
```

---

### 4. Скопировать файл

```
Copy file <path> to <path2>
```

Оригинал остаётся без изменений.

Пример:
```
Copy file governance/codex/SCHEMA_EXAMPLE.json to governance/codex/tasks/my_task.json
No issue comments.
```

---

### 5. Дописать в конец файла

```
Append to <path>: <content>
```

Добавляет строку/запись в конец. Работает для `.jsonl`, `.md`, `.txt`, `.log`.

Пример:
```
Append to governance/events/gpt_dev_runner.jsonl: {"event":"BEM526_TEST","trace":"bem526","at":"2026-05-17"}
No issue comments.
```

---

### 6. Дописать в начало файла

```
Prepend to <path>: <content>
```

Вставляет строку перед всем содержимым файла.

Пример:
```
Prepend to governance/reports/summary.md: '# Обновлено 2026-05-17'
No issue comments.
```

---

### 7. Обновить одно поле JSON

```
Set <path> field <key>=<value>
```

Читает JSON, обновляет поле, сохраняет. Автоматически обновляет `updated_at`.

Поддерживаемые типы: `true/false`, числа, строки.

Пример:
```
Set governance/state/role_cycle_state.json field status=completed
No issue comments.
```

---

### 8. Обновить несколько полей JSON

```
Set <path> fields: k1=v1, k2=v2, k3=v3
```

Пример:
```
Set governance/state/role_cycle_state.json fields: status=completed, current_role=null, updated_at=2026-05-17T09:00:00Z
No issue comments.
```

---

### 9. Заменить строку в файле

```
Replace in <path> line containing '<old>' with '<new>'
```

Находит все строки содержащие `<old>` и заменяет вхождение на `<new>`. Работает для YAML, JSON, MD, любых текстовых файлов.

Пример:
```
Replace in .github/workflows/role-orchestrator.yml line containing 'runs-on: ubuntu-18.04' with 'runs-on: ubuntu-latest'
No issue comments.
```

---

### 10. Удалить строки из файла

```
Delete from <path> line containing '<text>'
```

Удаляет все строки содержащие указанный текст.

Пример:
```
Delete from governance/state/routing.json line containing 'deprecated'
No issue comments.
```

---

### 11. Вставить строку после якоря

```
Insert in <path> after line containing '<anchor>': '<content>'
```

Вставляет строку сразу после каждой строки содержащей `<anchor>`.

Пример:
```
Insert in .github/workflows/claude.yml after line containing 'permissions:': '  contents: write'
No issue comments.
```

---

### 12. Создать директорию

```
Create dir <path>
```

Создаёт директорию с `.gitkeep` файлом (чтобы git её видел).

Пример:
```
Create dir governance/tasks/archive
No issue comments.
```

---

## Уровень 2 — Произвольный Python скрипт

Когда паттернов недостаточно — GPT пишет Python-скрипт прямо в objective.

### Синтаксис

```
Run script:
"""
# Python код здесь
# Полный доступ к файловой системе репозитория
import json
from pathlib import Path

data = json.loads(Path('governance/state/roadmap_state.json').read_text())
data['current_phase'] = 'P10'
data['phases_completed'].append('P9')
data['updated_at'] = '2026-05-17T09:00:00Z'
Path('governance/state/roadmap_state.json').write_text(json.dumps(data, indent=2))
changed_files.append('governance/state/roadmap_state.json')
"""
No issue comments.
```

### Что доступно в скрипте

```python
# Встроенные модули
import json       # работа с JSON
from pathlib import Path  # работа с файлами
import re         # регулярные выражения
import shutil     # копирование файлов

# Переменные контекста
now    # текущее время ISO-8601
trace  # trace_id текущей задачи
changed_files  # список — добавляй сюда изменённые файлы
ops_applied    # список — добавляй описание выполненных операций
```

### Безопасность — что запрещено в скрипте

```
❌ requests, urllib   — сетевые запросы
❌ subprocess         — запуск команд
❌ os.system          — системные команды
❌ socket             — сетевые соединения
❌ exec(), eval()     — динамическое выполнение
❌ os.environ         — чтение секретов
```

Если скрипт содержит запрещённые вызовы — executor вернёт `blocked: script_blocked`.

---

## Комбинирование операций

Можно использовать несколько паттернов и скрипт в одном objective:

```
Move file governance/tasks/pending/P9_TASK.md to governance/tasks/done/P9_TASK.md.
Set governance/state/roadmap_state.json fields: current_phase=P10, updated_at=2026-05-17T09:00:00Z.
Create file governance/reports/P9_completed.md with content '# P9 завершён. 2026-05-17'.
No issue comments.
```

---

## Как GPT выбирает инструмент — дерево решений

```
Задача:
│
├── Нужно создать/изменить/удалить файлы?
│   │
│   ├── Простая файловая операция (создать, переместить, удалить)?
│   │   └── → Паттерны 1-12
│   │
│   ├── Обновить JSON поле?
│   │   └── → Паттерн 7 или 8
│   │
│   ├── Исправить строку в YAML/workflow?
│   │   └── → Паттерн 9 (Replace in)
│   │
│   ├── Сложная логика (читать + анализировать + писать)?
│   │   └── → Уровень 2 (Run script)
│   │
│   └── Несколько операций сразу?
│       └── → Комбинирование паттернов
│
└── Нужно только прочитать файл?
    └── → MCP fetch_file (без Deno, без коммита)
```

---

## Шаблоны готовых скриптов

### Перевести задачу из pending в done и обновить roadmap

```
Move file governance/tasks/pending/<TASK>.md to governance/tasks/done/<TASK>.md.
Set governance/state/roadmap_state.json field updated_at=<ISO_DATE>.
No issue comments.
```

### Добавить задачу в roadmap

```
Run script:
"""
import json
from pathlib import Path

p = Path('governance/state/roadmap_state.json')
data = json.loads(p.read_text())
data['tasks'].append({
    'task_id': 'NEW_TASK_001',
    'status': 'pending',
    'note': 'Описание задачи'
})
data['updated_at'] = now
p.write_text(json.dumps(data, indent=2))
changed_files.append('governance/state/roadmap_state.json')
ops_applied.append('added task NEW_TASK_001 to roadmap')
"""
No issue comments.
```

### Обновить несколько state файлов сразу

```
Set governance/state/role_cycle_state.json fields: status=completed, current_role=null.
Set governance/state/roadmap_state.json field current_phase=P10.
Append to governance/events/gpt_dev_runner.jsonl: {"event":"PHASE_COMPLETE","phase":"P9","at":"<ISO_DATE>"}
No issue comments.
```

### Создать отчёт и зафиксировать результат

```
Create file governance/reports/<trace_id>.md with content '# Задача выполнена. <описание>. <ISO_DATE>'.
Move file governance/tasks/pending/<trace_id>.md to governance/tasks/done/<trace_id>.md.
No issue comments.
```

---

## Что возвращает executor в результате

```json
{
  "schema_version": 1,
  "trace_id": "...",
  "executor": "python-v3",
  "status": "completed | blocked | failed",
  "operations_applied": ["create:path", "set_field:path.key", "custom_script"],
  "changed_files": ["список файлов"],
  "commit_sha": "abc123...",
  "blocker": null,
  "completed_at": "ISO-8601"
}
```

**`operations_applied`** — список реально выполненных операций. Если список пустой при `completed` — objective не совпал ни с одним паттерном. Нужно проверить формат.

---

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `operations_applied` пустой | Паттерн не совпал | Проверить точный формат паттерна |
| `blocked: TASK_FILE_NOT_FOUND` | Task file не создан | Проверить `ok=true` от createCodexTask |
| `blocked: script_blocked` | Скрипт содержит запрещённые вызовы | Убрать requests/subprocess/os.system |
| `failed: Script error` | Ошибка в Python коде | Читать `blocker.message` — там traceback |
| `status=queued` 5+ мин | GitHub Actions не запустился | Проверить Actions в GitHub |

---

*BEM-526 | 2026-05-17 | Python executor v3*
