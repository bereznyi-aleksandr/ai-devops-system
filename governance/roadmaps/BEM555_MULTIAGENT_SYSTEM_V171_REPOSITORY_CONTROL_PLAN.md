# BEM-555 | Multiagent System v171 Repository-Control Plan

Дата: 2026-05-17 | 17:19 (UTC+3)

## 1. Цель

| Наименование | Описание | Обоснование |
|---|---|---|
| Проект | “Мультиагентная система” | Оператор запросил отдельное обсуждение плана доработок проекта |
| Основа | MASTER_PROMPT v171_CANON_FINAL | v171 определяет immutable HOW и active governance canon |
| Подход | Repository-control-first, затем реализация агента | Сначала state/registry/tests, потом product code |

## 2. Ключевые правила MASTER_PROMPT v171, которые меняют наш план

| Правило v171 | Значение для проекта | Действие |
|---|---|---|
| MASTER_PROMPT = HOW | Нельзя переписывать v171; новые версии только новым файлом | Создать inventory и derived plan, не менять master prompt |
| MASTER_PLAN.md = WHAT | Текущие задачи должны жить в mutable operational plan | Создать/обновить `governance/MASTER_PLAN.md` |
| Active state = runtime tasks index + task registry | `transport/results.jsonl` недостаточен как active routing canon | Создать `governance/runtime/tasks/index.json` и task files |
| SYSTEM writes active state | GPT не должен напрямую мутировать active state registry | Ввести controlled SYSTEM writer step |
| Active roles = EXECUTOR/AUDITOR/SYSTEM/OPERATOR | ANALYST не активная роль | Мигрировать analyst semantics в EXECUTOR planning |
| Active runtime = GitHub Actions + Claude Code Action | Старый Codex/Codespaces активный runtime запрещён в v171 | Подготовить Claude Code Action workflow layer |
| exchange ledger = historical archive | Нельзя делать active routing по ledger/старым transport artifacts | Развести historical evidence и active registry |

## 3. Предлагаемая новая схема работы

| Слой | Что делает | Файлы |
|---|---|---|
| Canon layer | Хранит immutable v171 и derived inventory | `governance/master_prompt/master_prompt_171_inventory.md` |
| Operational layer | Хранит текущий план работ | `governance/MASTER_PLAN.md` |
| Runtime registry | Хранит active routing state | `governance/runtime/tasks/index.json`, `governance/runtime/tasks/<ID>.json` |
| Artifact layer | Proposal/plan/decision/result/proofs | `governance/proposals/`, `governance/plans/`, `governance/decisions/`, `governance/proofs/` |
| Workflow layer | Runs executor/auditor/system checks | `.github/workflows/executor-runner.yml`, `auditor-runner.yml`, `autonomy-entrypoint.yml` |
| External reporting | Operator/Claude/GPT reports | `governance/reports/`, Telegram |

## 4. Roadmap BEM-555 — repository-control до реализации агента

| Этап | Название | Что сделать | PASS criteria |
|---|---|---|---|
| BEM-555.1 | v171 inventory | Инвентаризировать требования v171 и сопоставить с текущим repo | `master_prompt_171_inventory.md` |
| BEM-555.2 | MASTER_PLAN bootstrap | Создать `governance/MASTER_PLAN.md` как mutable WHAT | MASTER_PLAN has current roadmap and does not override v171 |
| BEM-555.3 | Runtime registry bootstrap | Создать `governance/runtime/tasks/index.json` + первый task file | SYSTEM-owned schema with idempotency/correlation |
| BEM-555.4 | Role model migration | Убрать active ANALYST terminology from new plan; map to EXECUTOR planning | Role lock doc updated |
| BEM-555.5 | Artifact directories | Создать proposals/plans/decisions/results/proofs structure | Directories and README/contracts exist |
| BEM-555.6 | SYSTEM state writer contract | Описать и реализовать controlled state writer | No GPT direct active state mutation |
| BEM-555.7 | Claude Code Action migration plan | Подготовить workflows under v171 active runtime model | workflow specs, no secrets in files |
| BEM-555.8 | Acceptance matrix | Тесты, без которых нельзя claim production | `governance/tests/multiagent_acceptance_matrix.md` |
| BEM-555.9 | Safe archive plan | Что архивировать из старых BEM/synthetic artifacts | archive manifest + no proof loss |
| BEM-555.10 | First product slice plan | Только после control layer — первый slice агента | task registry entry + proposal/plan |

## 5. Предлагаемая новая схема мультиагентной системы

| Компонент | v171-совместимая роль | Описание |
|---|---|---|
| EXECUTOR agent | Productive author | Создаёт proposal, plan, implementation, fix, rollback artifacts |
| AUDITOR agent | Review/decision | Проверяет EXECUTOR artifacts, пишет decision artifacts |
| SYSTEM agent/workflow | Routing/state authority | Валидирует, пишет runtime registry, запускает checks |
| OPERATOR | Emergency/setup | Не участвует в normal routing |
| GPT external assistant | External governance helper | Помогает оператору, готовит tasks/reports, но не является SYSTEM state writer |
| Claude Code Action | Active runtime executor/auditor | Согласно v171 active runtime |

## 6. Что НЕ делать сейчас

| Запрет | Почему |
|---|---|
| Не начинать agent product code напрямую | Нет v171 runtime registry/state foundation |
| Не использовать ANALYST как active role | v171 terminology lock запрещает |
| Не переписывать MASTER_PROMPT v171 | Immutable artifact |
| Не routing через exchange ledger / старые synthetic transport записи | v171 active routing = index.json + task registry |
| Не хранить secrets в repo | Контракт и v171 auth model |

## 7. Рекомендация GPT

| Наименование | Описание | Обоснование |
|---|---|---|
| Рекомендация | Начать BEM-555, не product implementation | v171 требует repository-control и runtime registry |
| Основной фокус | Привести репозиторий к v171 active canon | После этого мультиагент можно строить controlled slices |
| Следующее действие | BEM-555.1 v171 inventory | Самый безопасный первый шаг |
