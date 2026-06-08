# SYSTEM_STATUS.md
# Единый документ: что строим / что сделано / что осталось
# Обновляется GPT после каждого завершённого этапа. Читается в начале каждой сессии.

Последнее обновление: 2026-06-08
Статус системы: **WORKING_CONTOUR_NOT_READY**

---

## 1. ЧТО МЫ СТРОИМ — КОНЦЕПЦИЯ

### Управляющий контур (ai-devops-system)

Автономная мультиагентная система управления разработкой.
Оператор пишет задачу в Telegram — система выполняет её без участия человека.

### Иерархия объектов

```
ОПЕРАТОР (вне контура — только стратегия и gate-решения)
    ↓
ГЕНЕРАЛЬНЫЙ ДИРЕКТОР (GD)
    ├── GD.CURATOR       — принимает задачу от оператора, маршрутизирует
    ├── GD-C1            — контур правил
    └── GD-C2            — контур решений

    ↓
ДИРЕКТОР (DIR)
    ├── DIR.CURATOR      — доменный куратор
    ├── DIR-C1           — контур правил домена
    └── DIR-C2           — контур решений домена

    ↓
РАБОТНИК (WRK)
    ├── WRK.CURATOR      — выбирает рабочий контур
    ├── WRK-C1           — внутренний контур 1
    ├── WRK-C2           — внутренний контур 2
    └── WRK-C3           — внутренний контур 3 (минимум 3, максимум N)
```

### Внутри каждого WRK-Cx

```
ANALYST → AUDITOR.pre → EXECUTOR → AUDITOR.post → обратная связь куратору
```

Доработка — только через ANALYST. Горизонтальные связи — только через куратора-медиатора.

### Роли и провайдеры

| Роль | Провайдер | Примечание |
|---|---|---|
| GD.CURATOR | GPT Codex (подписка Plus) | Основной, Claude fallback при лимитах |
| DIR.CURATOR | GPT Codex | То же |
| WRK.CURATOR | GPT Codex | То же |
| ANALYST | GPT Codex | Анализирует задачу, строит план |
| AUDITOR | GPT Codex / Claude | Проверяет план и результат |
| EXECUTOR | GPT Codex / Claude | Выполняет задачу |

### Канонический runtime

- GitHub Actions (`codex-local.yml`) → self-hosted runner → Codex CLI
- Telegram polling каждые 5 минут (`telegram-poll.yml`)
- Все платные API (OpenAI HTTP, Gemini) — **ЗАПРЕЩЕНЫ** в production

---

## 2. ЧТО УЖЕ СДЕЛАНО ✅

### Инфраструктура

| Компонент | Статус | Доказательство |
|---|---|---|
| GitHub репозиторий | ✅ | bereznyi-aleksandr/ai-devops-system |
| GitHub Actions CI | ✅ | Workflows работают |
| `codex-local.yml` | ✅ | Поддерживает role=curator/analyst/auditor/executor |
| `telegram-poll.yml` | ✅ | Читает Telegram каждые 5 мин, диспатчит curator |
| `gpt-hosted-roles.yml` | ✅ ОТКЛЮЧЁН | ARCHIVED, платный API не вызывается |
| GitHub MCP/PAT для GPT | ✅ | GPT пишет в репо через Custom GPT |
| Mailbox Claude↔GPT | ✅ | `governance/audit_mailbox/` работает |
| `.gitignore` | ✅ ИСПРАВЛЕН | `governance/proofs/` больше не игнорируется |

### Python runners (библиотека и основные роли)

| Файл | Статус | Размер |
|---|---|---|
| `bem931_runner_lib.py` | ✅ Рабочий | 1622 байт |
| `gd_curator_runner.py` | ✅ Рабочий | 1049 байт |
| `dir_curator_runner.py` | ✅ Рабочий | 1080 байт |
| `wrk_curator_runner.py` | ✅ Рабочий | 1479 байт |
| `analyst_stage_runner.py` | ✅ Рабочий | 2051 байт |
| `auditor_stage_runner.py` | ✅ Рабочий | 2755 байт |
| `executor_stage_runner.py` | ✅ Рабочий | 2438 байт |

### Доказанные тесты (BEM-931 v3.6)

| Тест | Статус | github_run_id |
|---|---|---|
| RM-15: Live E2E цепочка GD→DIR→WRK→WRK-C1→ANALYST→AUDITOR→EXECUTOR→AUDITOR | ✅ PASS | 27116441198 |
| RM-16: WRK-C1, WRK-C2, WRK-C3 изолированно | ✅ PASS | 27116441198 |
| RM-17: Горизонтальный обмен через куратора-медиатора | ✅ PASS | 27116441198 |
| RM-18: Release gate (missing=[], failures=[]) | ✅ PASS | 27116441198 |

### Контракты и протоколы

| Документ | Статус |
|---|---|
| GPT_CONTRACT_v3.0 | ✅ Активен |
| BEM-931 v3.6 — согласован Claude | ✅ APPROVED |
| AGENT_CONTEXT.md v2.8 | ✅ Актуален |

---

## 3. ЧТО НЕ СДЕЛАНО ❌ — КРИТИЧЕСКИЕ GAPS

### GAP-1: Роли не подключены к Codex CLI через orchestrator

**Проблема:** `codex-local.yml` умеет запускать role=analyst/auditor/executor, но `role-orchestrator.yml` не диспатчит их через Codex по цепочке. Runners Python выполняются в CI как скрипты — без реального LLM внутри каждой роли.

**Что нужно:** Orchestrator должен вызывать `codex exec` с AGENTS.md промптом для каждой роли.

### GAP-2: AGENTS.md отсутствует

**Проблема:** Codex CLI читает AGENTS.md как постоянные инструкции. Без него каждая роль работает вслепую — не знает структуру каналов, как читать задачи, куда писать результат.

**Что нужно:** `AGENTS.md` в корне репо — инструкции для всех ролей системы.

### GAP-3: Система провайдеров не реализована

**Проблема:** Нет переключения GPT↔Claude при исчерпании лимитов. Нет `provider_config.json`.

**Что нужно:** `governance/config/provider_config.json` + логика в orchestrator.

### GAP-4: Telegram E2E не проверен

**Проблема:** Оператор пишет в Telegram → задача диспатчится → но ответ куратора оператору в Telegram не доказан live receipt с message_id.

**Что нужно:** Тест T-02 из протокола тестирования.

### GAP-5: WRK-C1/C2/C3 как Codex агенты не работают

**Проблема:** Контуры WRK-Cx проходят как Python-runners без LLM. Реального "думания" над задачей нет.

**Что нужно:** Каждый WRK-Cx должен получать задачу через Codex exec с промптом своей роли.

---

## 4. ДОРОЖНАЯ КАРТА — ЧТО ОСТАЛОСЬ СДЕЛАТЬ

### Критический путь (строгий порядок)

```
BEM-CODEX-001 → BEM-CODEX-002 → BEM-CODEX-003 → BEM-CODEX-004 → BEM-CODEX-005 → TEST-T02
```

| ID | Задача | Зависит от | Статус |
|---|---|---|---|
| BEM-CODEX-001 | Создать AGENTS.md — инструкции для Codex по структуре системы | — | IN_PROGRESS |
| BEM-CODEX-002 | Подключить ANALYST к Codex CLI через role-orchestrator | AGENTS.md | PENDING |
| BEM-CODEX-003 | Подключить AUDITOR к Codex CLI | BEM-CODEX-002 | PENDING |
| BEM-CODEX-004 | Подключить EXECUTOR к Codex CLI | BEM-CODEX-003 | PENDING |
| BEM-CODEX-005 | Система провайдеров: GPT primary, Claude fallback | BEM-CODEX-002 | PENDING |
| TEST-T02 | Live Telegram E2E: оператор пишет → система отвечает | BEM-CODEX-004 | PENDING |
| RELEASE | Release PASS + Claude external audit | TEST-T02 | BLOCKED |

### Acceptance критерий RELEASE

- [ ] Оператор пишет в Telegram → получает ответ через полную цепочку
- [ ] Каждая роль (ANALYST/AUDITOR/EXECUTOR) выполняется через `codex exec` с реальным LLM
- [ ] Провайдер GPT Codex через подписку Plus (не API ключ)
- [ ] При лимитах GPT — автоматический fallback на Claude
- [ ] Live receipts с github_run_id для всех шагов
- [ ] Claude external audit APPROVED

---

## 5. КАК ЧИТАТЬ ЭТОТ ДОКУМЕНТ

**GPT:** Читать в начале каждой сессии ВМЕСТО или ВМЕСТЕ с AGENT_CONTEXT.md.
После завершения этапа — обновить раздел 2 (сделано) и раздел 3 (осталось).

**Claude:** Использовать как baseline для аудита. Проверять соответствие реального состояния репо разделу 2.

**Оператор:** Раздел 3 — то что сейчас блокирует рабочую систему. Раздел 4 — порядок работ.

---

*Документ создан: Claude (EXTERNAL_AUDITOR_CLAUDE) | 2026-06-08*
*Следующее обновление: GPT после завершения BEM-CODEX-001*
