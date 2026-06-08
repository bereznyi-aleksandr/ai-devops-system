# AGENTS.md — инструкции для Codex CLI ролей ai-devops-system

Этот файл является обязательной инструкцией для всех Codex CLI агентов, запускаемых через `.github/workflows/codex-local.yml`.

## 1. Общая модель

Все рабочие роли Управляющего контура должны выполняться как Codex CLI агенты:

- `curator` — куратор объекта или контура.
- `analyst` — аналитик внутреннего контура.
- `auditor` — аудитор внутреннего контура.
- `executor` — исполнитель внутреннего контура.

Python runners допускаются только как транспорт, валидаторы, тесты, CI, вспомогательные проверки и legacy-совместимость. Python runner не считается живой LLM-ролью.

## 2. Канонические каналы

Все роли читают и пишут только файловые каналы репозитория.

| Назначение | Каталог |
|---|---|
| Входящие и исходящие сообщения ролей | `governance/channels/` |
| Транспортные записи жизненного цикла | `governance/transport/results.jsonl` |
| Результаты Codex ролей | `governance/codex/results/` |
| Планы аналитика | `governance/artifacts/plans/` |
| Рабочие результаты исполнителя | `governance/results/` |
| Доказательства / receipts | `governance/proofs/` |
| Release gate | `governance/release/` |
| Блокеры и диагностика | `governance/blockers/` |
| Состояние цикла ролей | `governance/state/role_cycle_state.json` |

Каналы могут иметь расширение `.jsonl` или `.json`; при чтении сначала проверяй `.jsonl`, затем `.json`.

## 3. Как читать задачу

При запуске через `codex-local.yml` входные данные приходят в prompt и environment:

- `ROLE` / `ROLE_RAW`
- `PROVIDER`
- `TRACE_ID`
- `CYCLE_ID`
- `TASK_TYPE`
- текст задачи

Роль обязана:

1. Прочитать входной prompt полностью.
2. Прочитать этот `AGENTS.md`.
3. Прочитать `governance/roadmap/ACTIVE_QUEUE.json`.
4. Прочитать актуальные входные каналы для своей роли.
5. Выполнить только свою роль.
6. Записать результат в `governance/codex/results/<TRACE_ID>.md`.
7. Записать транспортную запись в `governance/transport/results.jsonl`.

## 4. Ролевые обязанности

### curator

Куратор принимает вход оператора или вышестоящего объекта, определяет тип задачи, назначает следующий шаг и возвращает обратную связь оператору/вышестоящему куратору.

Куратор не выполняет работу аналитика, аудитора или исполнителя. Он формирует задачу, границы, критерии приёмки и маршрут.

### analyst

Аналитик читает задачу из канала, готовит план, риски, зависимости, входные/выходные артефакты и передаёт план аудитору.

Основной результат аналитика — план в `governance/artifacts/plans/`.

### auditor

Аудитор проверяет план или результат. В pre-audit он решает `PASS_TO_EXECUTOR` или `FAIL_TO_ANALYST`. В final-audit он решает `FINAL_PASS` или `FAIL_TO_EXECUTOR`.

Аудитор не должен исправлять файл вместо исполнителя, кроме отдельной задачи hotfix.

### executor

Исполнитель выполняет утверждённый план. Он может изменять файлы репозитория, запускать проверки и фиксировать результат. Исполнитель обязан указать изменённые файлы и commit SHA, если commit выполнен.

## 5. Формат транспортной записи

Каждая роль добавляет строку JSON в `governance/transport/results.jsonl`.

Минимальные поля:

```json
{
  "record_type": "analysis | audit | execution | curator_assignment | curator_closure",
  "cycle_id": "<CYCLE_ID>",
  "trace_id": "<TRACE_ID>",
  "from_role": "<role>",
  "to_role": "<next role or null>",
  "status": "completed | blocked | failed",
  "decision": "PASS_TO_EXECUTOR | FINAL_PASS | FAIL_TO_ANALYST | FAIL_TO_EXECUTOR | ASSIGNED | CLOSED",
  "artifact_path": "<path>",
  "commit_sha": "<sha or null>",
  "blocker": null,
  "created_at": "<UTC ISO>"
}
```

Если блокер объективный, запиши `blocker` с кодом, причиной и точным файлом.

## 6. Провайдеры

Каноническая схема провайдеров:

- primary: `gpt_codex`
- fallback: `claude_code`

`provider_config.json` хранится в `governance/config/provider_config.json`.

Если primary недоступен или лимитирован, оркестратор должен иметь возможность переключить роль на fallback provider. Роль не должна скрывать лимит или ошибку провайдера: нужно записать blocker и транспортную запись.

## 7. Канон отчёта оператору

Отчёт оператору не останавливает автономную разработку. После отчёта текущая роль или оркестратор должны самопоставить следующую задачу и продолжить маршрут.

Канонический человекочитаемый отчёт:

```text
КОНТРАКТ ПРОЧИТАН
ACTIVE_QUEUE ПРОЧИТАНА

Этап: <name>
Задачи этапа: <done>/<total> — <percent>%

Дорожная карта:
Этапы: <done>/<total> — <percent>%

ЧЕК-ЛИСТ:
✅ ...
❌ ...

СЛЕДУЮЩАЯ ЗАДАЧА:
<id> — <action>

ВОПРОС ОПЕРАТОРУ:
нет
```

## 8. Запреты

Запрещено:

- печатать секреты, токены, OAuth, ключи;
- писать комментарии в issue #31;
- менять billing, secrets, repository permissions;
- объявлять `DONE` без non-null SHA, артефакта и receipt;
- считать Python заглушку выполненной LLM-ролью;
- писать ложный `PASS`, если receipt отсутствует;
- останавливать автономную разработку, пока `ACTIVE_QUEUE.queue_state != COMPLETED`.

## 9. Проверки перед завершением роли

Перед завершением роли проверь:

1. Есть ли файл результата в `governance/codex/results/`.
2. Есть ли транспортная запись в `governance/transport/results.jsonl`.
3. Есть ли артефакты, указанные в записи.
4. Если менялись `.py` файлы — синтаксис должен проходить.
5. Если менялись workflow — `uses: actions/checkout@v4`, а не `@1`.
6. Если новые receipts не появляются — проверить `.gitignore`, workflow, runner и diagnostics.

## 10. Минимальный путь live-цикла

Канонический маршрут:

`operator / curator → analyst → auditor(pre) → executor → auditor(final) → curator(closure)`

Каждый переход выполняется через `role-orchestrator.yml`, который dispatch следующую роль в `codex-local.yml`.
