# MASTER PLAN — AI DevOps System
Версия: v2.1 | Дата: 2026-05-02

## НАЗНАЧЕНИЕ ФАЙЛА
Главный управляющий документ системы.
Все роли читают этот файл перед каждым действием.
Обновляется оператором при изменении целей и приоритетов.

## ТЕКУЩИЙ ЭТАП
E3 — Отладка и стабилизация автономного цикла

## АКТИВНАЯ ЗАДАЧА
Подтвердить первый полный автономный цикл @analyst → @auditor → @executor.

## ДОРОЖНАЯ КАРТА

| Шаг | Название | Статус |
|---|---|---|
| E1 | Очистка репозитория | DONE |
| E2 | Dual scheduler + autonomous infrastructure | DONE |
| E3 | Отладка и стабилизация | IN PROGRESS |
| E4 | Мультиагентный контур | TODO |

## АРХИТЕКТУРА СИСТЕМЫ

### Основной контур (Claude)
@analyst → analyst.yml
@auditor → auditor.yml
@executor → executor.yml
@claude → claude.yml

### Резервный контур (GPT/Codex)
Активируется только при недоступности Claude Code и owner approval.
@codex ROLE=GPT_ANALYST / GPT_AUDITOR / GPT_EXECUTOR

### State layer
- governance/EXCHANGE.md — текущее состояние ISA (человеко-читаемое)
- governance/exchange.jsonl — журнал событий (машинный)

### Legacy (архив)
- governance/archive/legacy-2026-05-01/exchange_ledger.csv — устаревший CSV

## КАНОН ОТЧЁТА (обязателен для всех ролей)

```
BEM-XXX | РОЛЬ | дата UTC | время UA (UTC+3)

Этап: X/Y — XX%
Дорожная карта: X/Y — XX%

Чек-лист:
✅ ...
❌ ... (если есть)

| Тип | Задача | Комментарий |
|---|---|---|
| Выполнено | ... | ... |
| Следующая задача | ... | ... |

БЛОКЕРЫ: ... (если есть)
СЛЕДУЮЩИЙ ОТЧЁТ UA: HH:MM
```

Формат времени:
- UTC: 2026-05-02T11:31:00Z
- UA (UTC+3): 14:31

## GPT-КУРАТОР ISA

### Регламент
Контрольный цикл: 1 раз в час / каждые 60 минут

### Что читает каждый час
1. GitHub issue #31 — последние комментарии
2. GitHub Actions — последние runs
3. Pull Requests — новые/draft PR
4. governance/MASTER_PLAN.md
5. governance/EXCHANGE.md
6. governance/exchange.jsonl

### Формат отчёта куратора

```
BEM-XXX | GPT-КУРАТОР ISA | дата UTC | время UA (UTC+3)

Выполнение этапа: X/Y (%)
Выполнение дорожной карты: X/Y (%)

| Выполненное действие | Следующее планируемое действие | Краткий комментарий |
|---|---|---|
| ... | ... | ... |

БЛОКЕРЫ: ...
СЛЕДУЮЩЕЕ КЛЮЧЕВОЕ ДЕЙСТВИЕ: ...
ТРЕБУЕТСЯ РАЗРЕШЕНИЕ ВЛАДЕЛЬЦА: да/нет
СЛЕДУЮЩИЙ ОТЧЁТ UA: HH:MM
```

### Что куратор может без owner approval
- Читать issue/Actions/PR/MASTER_PLAN/EXCHANGE/exchange.jsonl
- Формировать BEM-отчёт
- Предлагать следующий шаг

### Что требует owner approval
- Переключение контура Claude → GPT/Codex
- Обратное переключение GPT/Codex → Claude
- Любые действия в репозитории

## FALLBACK GPT/CODEX CONTOUR

Условия предложения (одно из):
1. Claude Code usage limit reached
2. Claude Code Action temporarily unavailable
3. Primary contour завис более одного часового цикла

Переключение фиксируется в EXCHANGE.md и exchange.jsonl.
GPT_EXECUTOR создаёт только draft PR — merge только владелец.

## AUTONOMOUS CURATOR PROTOCOL
Обязательный алгоритм: governance/AUTONOMOUS_CURATOR_PROTOCOL.md
Цикл: plan → act → check → report → next action
Правило двух пустых проверок: после 2 неуспешных → BLOCKER → corrective action

## ПРАВИЛА ДЛЯ АНАЛИТИКА
1. Читать этот файл перед каждым действием
2. Читать governance/EXCHANGE.md
3. Определить следующий шаг по дорожной карте
4. Сформировать задание для АУДИТОРА
5. Не выполнять изменения в коде

## ПРАВИЛА ДЛЯ АУДИТОРА
1. Читать этот файл перед каждым решением
2. Читать governance/EXCHANGE.md
3. Проверять самостоятельно — не доверять объяснениям
4. Давать только APPROVED или BLOCKED
5. Не придумывать задачи

## ПРАВИЛА ДЛЯ ИСПОЛНИТЕЛЯ
1. Читать этот файл перед каждым действием
2. Читать governance/EXCHANGE.md
3. Выполнять только то что одобрил АУДИТОР
4. Записывать события в governance/exchange.jsonl
5. Не делать более одного шага за цикл

## ИСТОРИЯ ВЫПОЛНЕНИЯ

| Дата | Шаг | Роль | Результат |
|---|---|---|---|
| 2026-05-01 | Инициализация системы | SYSTEM | SUCCESS |
| 2026-05-01 | Создан state layer | АУДИТОР | SUCCESS |
| 2026-05-01 | Исправлены workflows | АУДИТОР | SUCCESS |
| 2026-05-02 | Dual scheduler создан | АУДИТОР | SUCCESS |
| 2026-05-02 | AUTONOMOUS_CURATOR_PROTOCOL создан | АУДИТОР | SUCCESS |
| 2026-05-02 | Канон отчёта — добавлено время UA | АУДИТОР | SUCCESS |
