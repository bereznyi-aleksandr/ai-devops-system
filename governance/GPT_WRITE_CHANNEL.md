# GPT WRITE CHANNEL — ai-devops-system

**BEM-526** | Версия: 3.0 | 2026-05-17

---

## Принцип работы

**GPT думает. Python executor делает.**

GPT читает задачу, анализирует репозиторий через MCP, формулирует objective, отправляет через Deno. Python executor выполняет операции с файлами и делает коммит в репозиторий. Никакого платного API. Никаких ограничений по типам задач.

---

## Алгоритм

```
1. Сформулировать objective с нужными паттернами
2. createCodexTask(trace_id, task_type, title, objective)
3. Проверить: ok=true + dispatch=204
4. Подождать 1-3 минуты
5. getCodexStatus(trace_id)
6. Проверить operations_applied — там список реально выполненных операций
7. Если нужно — прочитать результат через MCP fetch_file
```

**Важно:** если `operations_applied` пустой при `completed` — objective не совпал с паттерном. Проверить формат.

**Максимум 2 вызова getCodexStatus подряд. Затем — blocker, не продолжать.**

---

## Уровень 1 — Паттерны (12 операций)

Вставить в objective нужные строки. Всегда заканчивать: `No issue comments.`

| # | Паттерн | Что делает |
|---|---|---|
| 1 | `Create file <path> with content <text>` | Создать файл |
| 2 | `Delete file <path>` | Archived-маркер |
| 3 | `Move file <path> to <path2>` | Переместить |
| 4 | `Copy file <path> to <path2>` | Скопировать |
| 5 | `Append to <path>: <content>` | Дописать в конец |
| 6 | `Prepend to <path>: <content>` | Дописать в начало |
| 7 | `Set <path> field <key>=<value>` | Обновить поле JSON |
| 8 | `Set <path> fields: k1=v1, k2=v2` | Обновить несколько полей JSON |
| 9 | `Replace in <path> line containing '<old>' with '<new>'` | Заменить строку |
| 10 | `Delete from <path> line containing '<text>'` | Удалить строки |
| 11 | `Insert in <path> after line containing '<anchor>': '<content>'` | Вставить строку |
| 12 | `Create dir <path>` | Создать директорию |

Паттерны можно **комбинировать** в одном objective.

---

## Уровень 2 — Произвольный Python скрипт

Когда паттернов недостаточно — GPT пишет Python-скрипт в objective:

```
Run script:
"""
import json
from pathlib import Path

# Любой Python код для работы с файлами репозитория
data = json.loads(Path('governance/state/roadmap_state.json').read_text())
data['current_phase'] = 'P10'
data['updated_at'] = now  # переменная доступна автоматически
Path('governance/state/roadmap_state.json').write_text(json.dumps(data, indent=2))
changed_files.append('governance/state/roadmap_state.json')
"""
No issue comments.
```

Доступные переменные в скрипте: `json`, `Path`, `re`, `shutil`, `now`, `trace`, `changed_files`, `ops_applied`.

Запрещено в скрипте: `requests`, `urllib`, `subprocess`, `os.system`, `socket`.

---

## Дерево решений — как выбрать паттерн

```
Что нужно сделать?
│
├── Создать новый файл → паттерн 1
├── Удалить файл → паттерн 2
├── Переместить файл (например из pending в done) → паттерн 3
├── Скопировать файл → паттерн 4
├── Добавить запись в jsonl/log → паттерн 5
├── Обновить поле в JSON → паттерн 7
├── Обновить несколько полей JSON → паттерн 8
├── Исправить строку в YAML/workflow/любом файле → паттерн 9
├── Удалить строку из файла → паттерн 10
├── Вставить строку в нужное место → паттерн 11
├── Создать директорию → паттерн 12
├── Сложная логика (читать+анализировать+писать) → Run script
└── Несколько операций сразу → комбинирование паттернов
```

---

## Готовые шаблоны для типовых задач

### Завершить задачу и обновить roadmap
```
Move file governance/tasks/pending/<TASK>.md to governance/tasks/done/<TASK>.md.
Set governance/state/roadmap_state.json field updated_at=<ISO_DATE>.
No issue comments.
```

### Обновить статус JSON файла
```
Set governance/state/role_cycle_state.json fields: status=completed, current_role=null.
No issue comments.
```

### Исправить строку в workflow
```
Replace in .github/workflows/<file>.yml line containing '<старая строка>' with '<новая строка>'
No issue comments.
```

### Добавить событие в журнал
```
Append to governance/events/gpt_dev_runner.jsonl: {"event":"<EVENT>","trace":"<TRACE>","at":"<ISO>"}
No issue comments.
```

### Создать отчёт и закрыть задачу
```
Create file governance/reports/<trace>.md with content '# <Заголовок>. Выполнено <дата>.'.
Move file governance/tasks/pending/<trace>.md to governance/tasks/done/<trace>.md.
No issue comments.
```

### Сложное обновление roadmap через скрипт
```
Run script:
"""
import json
from pathlib import Path

p = Path('governance/state/roadmap_state.json')
data = json.loads(p.read_text())
# Найти задачу и обновить статус
for task in data.get('tasks', []):
    if task.get('task_id') == 'TASK_ID_HERE':
        task['status'] = 'completed'
        task['completed_at'] = now
data['updated_at'] = now
p.write_text(json.dumps(data, indent=2))
changed_files.append('governance/state/roadmap_state.json')
ops_applied.append('updated task status in roadmap')
"""
No issue comments.
```

---

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `operations_applied` пустой | Паттерн не совпал | Проверить точный формат — кавычки, регистр |
| `blocked: TASK_FILE_NOT_FOUND` | createCodexTask не создал файл | Проверить `ok=true` в ответе Deno |
| `blocked: script_blocked` | Запрещённые вызовы в скрипте | Убрать requests/subprocess/os.system |
| `failed: Script error` | Ошибка Python | Читать `blocker.message` — там traceback |
| `ok=false, rate_limited` | Слишком частые запросы | Ждать 60 секунд |
| `status=queued` 5+ мин | Runner занят или не запустился | Проверить GitHub Actions |

---

## Полная документация

`governance/codex/PYTHON_EXECUTOR_GUIDE.md` — все паттерны с примерами, шаблоны скриптов, диагностика.

---

*BEM-526 | 2026-05-17 | v3.0*
