# SYSTEM_STATUS.md v2.0
# ФИНАЛЬНАЯ АРХИТЕКТУРА | СТАТУС | ДОРОЖНАЯ КАРТА
# Обновляется GPT после каждой завершённой задачи.
# Читается ПЕРВЫМ в начале каждой сессии.

Последнее обновление: 2026-06-08
Статус: **WORKING_CONTOUR_NOT_READY**
Release: **BLOCKED**

---

## 1. ФИНАЛЬНАЯ АРХИТЕКТУРА

### Концепция
Автономная мультиагентная система. Оператор пишет в Telegram — система выполняет без участия человека через цепочку Codex CLI агентов.

### Иерархия объектов
```
ОПЕРАТОР (вне контура — только стратегия, только Telegram)
    ↓
GD (Генеральный директор)
    ├── GD.CURATOR       — принимает от оператора, маршрутизирует в DIR
    ├── GD-C1            — контур правил
    └── GD-C2            — контур решений
    ↓
DIR (Директор)
    ├── DIR.CURATOR      — доменный куратор
    ├── DIR-C1           — правила домена
    └── DIR-C2           — решения домена
    ↓
WRK (Работник)
    ├── WRK.CURATOR      — выбирает контур
    ├── WRK-C1           — внутренний контур 1
    ├── WRK-C2           — внутренний контур 2
    └── WRK-C3           — внутренний контур 3 (минимум 3)
```

### Внутри каждого WRK-Cx
```
ANALYST → AUDITOR.pre → EXECUTOR → AUDITOR.post → feedback → WRK.CURATOR
```
Доработка — только через ANALYST.
Горизонталь — только через куратора-медиатора.

### Роли и провайдеры
| Роль | Primary | Fallback |
|---|---|---|
| GD.CURATOR | GPT Codex (ChatGPT Plus OAuth) | Claude Code |
| DIR.CURATOR | GPT Codex | Claude Code |
| WRK.CURATOR | GPT Codex | Claude Code |
| ANALYST | GPT Codex | Claude Code |
| AUDITOR | GPT Codex / Claude | — |
| EXECUTOR | GPT Codex / Claude | — |

**ЗАПРЕЩЕНО:** OPENAI_API_KEY, Gemini API — только Codex через подписку Plus.

### Технический стек
| Компонент | Технология | Статус |
|---|---|---|
| Входящий канал | Telegram + Cloudflare Worker webhook | ⚠️ CF не задеплоен |
| Резерв polling | telegram-poll.yml cron 5 мин | ✅ Работает |
| LLM runtime | codex-local.yml → Codex CLI | ✅ Активен |
| Инструкции Codex | AGENTS.md корень репо | ❌ Не создан |
| Оркестратор | role-orchestrator.yml | ⚠️ Не подключён к Codex |
| Каналы | governance/channels/ jsonl | ✅ Работают |
| Провайдер система | provider_config.json | ❌ Не создана |
| Исходящий Telegram | curl sendMessage из codex exec | ❌ Не реализован |

---

## 2. ЧТО СДЕЛАНО

| Компонент | Статус | Доказательство |
|---|---|---|
| GitHub репозиторий | ✅ | main branch |
| codex-local.yml | ✅ | role=curator/analyst/auditor/executor |
| telegram-poll.yml | ✅ | Работает |
| gpt-hosted-roles.yml | ✅ АРХИВ | Платный API отключён |
| GitHub MCP/PAT для GPT | ✅ | Custom GPT пишет в репо |
| Mailbox Claude↔GPT | ✅ | governance/audit_mailbox/ |
| .gitignore исправлен | ✅ | SHA 73231b2e |
| CF Worker код | ✅ | infrastructure/cloudflare-worker/ |
| bem931_runner_lib.py | ✅ | 1622 байт |
| gd_curator_runner.py | ✅ | 1049 байт |
| dir_curator_runner.py | ✅ | 1080 байт |
| wrk_curator_runner.py | ✅ | 1479 байт |
| analyst_stage_runner.py | ⚠️ БЕЗ LLM | 2051 байт — Python без codex exec |
| auditor_stage_runner.py | ⚠️ БЕЗ LLM | 2755 байт — Python без codex exec |
| executor_stage_runner.py | ⚠️ БЕЗ LLM | 2438 байт — Python без codex exec |
| RM-15 Live E2E | ✅ PASS | github_run_id 27116441198 |
| RM-16 WRK-C1/C2/C3 | ✅ PASS | github_run_id 27116441198 |
| RM-17 Горизонталь | ✅ PASS | github_run_id 27116441198 |
| RM-18 Release gate | ✅ PASS | missing=[], failures=[] |
| GPT Contract v3.0 | ✅ | governance/curator/GPT_CONTRACT_v3_0.md |

**Важно:** RM-15..18 доказывают работу файловых каналов. НЕ доказывают LLM внутри ролей.

---

## 3. КРИТИЧЕСКИЕ GAPS

| # | Gap | Проблема | Что нужно |
|---|---|---|---|
| GAP-1 КРИТИЧЕСКИЙ | AGENTS.md отсутствует | Codex не знает структуру каналов, роли, форматы | AGENTS.md > 500 байт в корне репо |
| GAP-2 КРИТИЧЕСКИЙ | Роли без LLM | ANALYST/AUDITOR/EXECUTOR — Python без codex exec | role-orchestrator вызывает codex exec для каждой роли |
| GAP-3 | Нет исходящего Telegram | Оператор не получает ответ автоматически | curl sendMessage из codex exec в конце задачи |
| GAP-4 | Нет системы провайдеров | При лимитах GPT — падение без fallback | provider_config.json + логика в orchestrator |
| GAP-5 | CF Worker не задеплоен | Задержка 5 мин вместо мгновенного webhook | Задеплоить CF Worker, зарегистрировать webhook |

---

## 4. ДОРОЖНАЯ КАРТА

Строгий порядок. DONE только с live receipt (github_run_id).

| # | ID | Задача | Depends on | Acceptance | Статус |
|---|---|---|---|---|---|
| 1 | BEM-CODEX-001 | Создать AGENTS.md | — | > 500 байт, каналы+роли+провайдеры+Telegram формат | IN_PROGRESS |
| 2 | BEM-CODEX-002 | ANALYST → Codex exec | AGENTS.md | codex exec, план специфичен для задачи, receipt | PENDING |
| 3 | BEM-CODEX-003 | AUDITOR → Codex exec | BEM-CODEX-002 | codex exec, содержательный вердикт, receipt | PENDING |
| 4 | BEM-CODEX-004 | EXECUTOR → Codex exec | BEM-CODEX-003 | codex exec, реальный коммит, commit_sha, receipt | PENDING |
| 5 | BEM-CODEX-005 | Исходящий Telegram | BEM-CODEX-001 | curl sendMessage из curator, message_id в receipt | PENDING |
| 6 | BEM-CODEX-006 | Система провайдеров | BEM-CODEX-002 | provider_config.json, fallback Claude при лимитах | PENDING |
| 7 | BEM-CF-001 | Задеплоить CF Worker | — | CF онлайн, webhook < 1 сек, getWebhookInfo OK | PENDING |
| 8 | TEST-T02 | Live Telegram E2E | BEM-CODEX-005 | Оператор пишет → ответ, 7 receipts, Claude APPROVED | PENDING |
| 9 | RELEASE | Release PASS | TEST-T02 | WORKING_CONTOUR_READY | BLOCKED |

---

## 5. ПРАВИЛА РАБОТЫ С ДОКУМЕНТОМ

**GPT:** читать в начале сессии. После DONE задачи — обновить разделы 2, 3, 4.
**Claude:** проверять раздел 2 на соответствие репо при аудите.
**Оператор:** раздел 3 = что блокирует. Раздел 4 = что строим.

*Финальная редакция v2.0 | Claude | 2026-06-08*
