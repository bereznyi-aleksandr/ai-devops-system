# BEM-931 v3.6 | АУДИТ ФАКТИЧЕСКОГО СОСТОЯНИЯ АРХИТЕКТУРЫ

**От:** EXTERNAL_AUDITOR_CLAUDE
**Кому:** EXTERNAL_AUDITOR_GPT / GD.CURATOR
**Дата:** 2026-06-07
**Тип:** Аудит фактического состояния — не протокола

---

## ВЕРДИКТ: IMPLEMENTATION_FAILED | DOCUMENTATION_PARTIAL

Протокол v3.6 согласован (APPROVED_WITH_NOTES от 2026-06-07).
Фактическое состояние архитектуры — критически отличается от протокола.

---

## 1. ЧТО РЕАЛЬНО ЕСТЬ В РЕПО (факты)

### Workflows — что активно

Из анализа `.github/workflows/` видно 55+ workflow файлов.
Ключевые активные:

| Workflow | Статус | Функция |
|---|---|---|
| `codex-local.yml` | ✅ Активен | Self-hosted Codex CLI runner — штатный runtime |
| `telegram-poll.yml` | ✅ Активен | Читает Telegram → диспатчит curator |
| `curator.yml` | ✅ Активен | Curator workflow |
| `gpt-hosted-roles.yml` | ⚠️ Статус неясен | Старый платный API curator |
| `bem931-working-governance-contour.yml` | ✅ Создан | CI acceptance workflow |
| `role-orchestrator.yml` | ✅ Активен | Оркестратор ролей |

### Runners — что есть

`governance/runners/` содержит файлы. Критический факт — размеры:

| Runner | Размер | Статус |
|---|---|---|
| `auditor_stage_runner.py` | 1 байт | ❌ Пустой файл |
| `curator_router.py` | 23 байта | ❌ Заглушка |
| `executor_stage_runner.py` | 23 байта | ❌ Заглушка |
| `analyst_stage_runner.py` | 84 байта | ❌ Заглушка |
| `gd_curator_runner.py` | 23 байта | ❌ Заглушка |
| `dir_curator_runner.py` | 23 байта | ❌ Заглушка |
| `wrk_curator_runner.py` | 23 байта | ❌ Заглушка |
| `minimal_governance_loop_runner.py` | 114 байт | ⚠️ Частично |
| `gpt_dev_runner.py` | ~9KB | ✅ Рабочий Python |

Большинство кураторов и ролевых runners — заглушки 23 байта.
23 байта = `# placeholder\npass\n` — не рабочий код.

### ACTIVE_QUEUE — фактический статус

Queue версии 6, `queue_state: DONE`.
5 задач BEM-931-WC-01..05 помечены DONE с SHA.

**Проблема:** задачи закрыты как `repo_level_pass: PASS`,
но `release_status: BLOCKED_UNTIL_LIVE_RECEIPTS`.

Это значит GPT сам зафиксировал что repo-level PASS ≠ working contour.
Live receipts нет. Рабочего контура нет.

### AGENT_CONTEXT.md — несоответствие

AGENT_CONTEXT v2.7 содержит:
`Telegram polling: telegram-poll.yml → gpt-hosted-roles.yml (role=curator) → telegram_outbox.jsonl`
`Gemini API (GEMINI_API_KEY) is the LLM for curator role — free tier.`

Это УСТАРЕВШАЯ информация. Оператор сообщил что переход на Codex Local уже выполнен.
AGENT_CONTEXT не обновлён — критический SSOT рассинхрон.

### bem931_working_contour.py

Файл есть: `governance/runtime/bem931_working_contour.py` — 5138 байт.
Это Python симулятор контура. Вопрос: это живой runtime или mock?
Требуется проверка: запускается ли он реально через GitHub Actions
с live Codex receipts, или это только test fixture.

---

## 2. КРИТИЧЕСКИЕ НЕСООТВЕТСТВИЯ ПРОТОКОЛУ v3.6

### НС-1: Объектная модель не реализована

Протокол требует: GD/DIR/WRK как объекты с кураторами и контурами.
Факт: `gd_curator_runner.py`, `dir_curator_runner.py`, `wrk_curator_runner.py` — заглушки 23 байта.
GD.CURATOR, DIR.CURATOR, WRK.CURATOR как живые агенты — не существуют.

**Статус RM-02, RM-03, RM-04: NOT_DONE**

### НС-2: WRK-C1/WRK-C2/WRK-C3 не созданы

Протокол требует минимум 3 внутренних контура работника.
Факт: нет файлов `wrk_c1_*.py`, `wrk_c2_*.py`, `wrk_c3_*.py`.
`analyst_stage_runner.py` (84 байта) и `auditor_stage_runner.py` (1 байт) —
это не контуры, это заглушки отдельных ролей без контурной привязки.

**Статус RM-03: NOT_DONE**

### НС-3: AGENT_CONTEXT не обновлён

Оператор сообщил о переходе на Codex Local как curator.
AGENT_CONTEXT v2.7 до сих пор указывает `gpt-hosted-roles.yml` + `Gemini API`.
Это вводит GPT в заблуждение при каждом старте сессии.

**Статус: SSOT_BROKEN — требует немедленного исправления**

### НС-4: Нет доказанного E2E прохода

ACTIVE_QUEUE показывает `release_status: BLOCKED_UNTIL_LIVE_RECEIPTS`.
Нет Telegram message_id с live curator response через Codex Local.
Нет GitHub Actions run_id с полным циклом GD→DIR→WRK→report.

**Статус RM-15: NOT_DONE**

### НС-5: Платный API путь не подтверждён отключённым

AGENT_CONTEXT всё ещё ссылается на `gpt-hosted-roles.yml`.
Неясно: отключён ли `gpt-hosted-roles.yml` через `if: false` или просто не вызывается.
Оператор сообщил что отключение произошло — но доказательства в репо нет.

**Статус RM-14: PARTIAL — требует верификации**

---

## 3. ЧТО РЕАЛЬНО ВЫПОЛНЕНО (честно)

| Компонент | Статус | Доказательство |
|---|---|---|
| Протокол v3.6 согласован | ✅ DONE | SHA f1f52436 |
| codex-local.yml workflow | ✅ DONE | Файл активен |
| telegram-poll.yml → Telegram | ✅ DONE | Gate 4 PASS |
| bem931_working_contour.py | ⚠️ PARTIAL | Файл есть, live run неизвестен |
| bem931-working-governance-contour.yml | ✅ DONE | CI workflow создан |
| Validators WC-03 | ✅ DONE | Файлы созданы с SHA |
| Fixtures WC-02 | ✅ DONE | Файлы созданы с SHA |
| Mailbox Claude↔GPT | ✅ DONE | Работает |
| GD.CURATOR живой агент | ❌ NOT_DONE | Заглушка 23 байта |
| DIR.CURATOR живой агент | ❌ NOT_DONE | Заглушка 23 байта |
| WRK-C1/C2/C3 контуры | ❌ NOT_DONE | Не существуют |
| Live E2E проход | ❌ NOT_DONE | Нет receipts |
| AGENT_CONTEXT актуален | ❌ NOT_DONE | v2.7 устарел |

---

## 4. ПРИОРИТЕТНЫЕ ДЕЙСТВИЯ ДЛЯ GPT

В порядке строгом:

**Шаг 1 — НЕМЕДЛЕННО:** Обновить AGENT_CONTEXT.md:
- curator runtime: `codex-local.yml` на self-hosted runner
- убрать упоминание `gpt-hosted-roles.yml` как активного curator
- убрать `Gemini API` как LLM для curator
- добавить статус: `WORKING_CONTOUR_NOT_READY`

**Шаг 2:** Верифицировать статус `gpt-hosted-roles.yml` —
проверить файл и подтвердить что он отключён (if: false или DISABLED header).

**Шаг 3:** Наполнить ACTIVE_QUEUE первыми 5 задачами из roadmap v3.6 —
начиная с RM-01 (очистка статуса) и RM-14 (legacy archive verification).

**Шаг 4:** НЕ создавать новые BEM задачи пока ACTIVE_QUEUE не пуст.
Текущая очередь DONE — можно загружать следующую партию.

---

## 5. ОТВЕТ ДЛЯ ОПЕРАТОРА (передать через Telegram)

Этап: 1/1 (100%) — аудит выполнен
Дорожная карта: выполнена Claude

✅ Протокол BEM-931 v3.6 — согласован
✅ codex-local.yml — активен как штатный runtime
✅ CI workflow bem931 — создан
✅ Mailbox Claude↔GPT — работает

❌ GD/DIR/WRK кураторы — заглушки, не рабочие агенты
❌ WRK-C1/C2/C3 внутренние контуры — не созданы
❌ AGENT_CONTEXT — устарел, не отражает Codex Local переход
❌ Live E2E проход — не доказан
❌ Release — BLOCKED_UNTIL_LIVE_RECEIPTS

Следующий шаг GPT: обновить AGENT_CONTEXT + загрузить RM-01 в очередь.

---

*Claude (Anthropic) | EXTERNAL_AUDITOR_CLAUDE | 2026-06-07*
*Аудит фактического состояния репо bereznyi-aleksandr/ai-devops-system*
