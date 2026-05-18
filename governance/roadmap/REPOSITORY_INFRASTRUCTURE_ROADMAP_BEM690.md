# BEM-690 | Repository Architecture Vision

Дата: 2026-05-18 | 19:34 (UTC+3)
Статус: DRAFT_READY

## Короткий вывод
Репозиторий должен развиваться как control-plane автономной бизнес-системы, а не как обычный code repo. Код продуктов может жить внутри `products/` на первом этапе, но управление, аудит, роли, runtime registry и отчёты должны жить отдельно в `governance/` и `agents/`.

## Целевая структура
```
/
├── README.md
├── docs/                              # human documentation, product docs, operator docs
│   ├── architecture/
│   ├── operator/
│   └── runbooks/
├── governance/                        # control plane of the autonomous system
│   ├── protocols/                     # каноны и правила
│   ├── roadmap/                       # стратегические и BEM-дорожные карты
│   ├── runtime/                       # registry v2: источник истины
│   │   ├── tasks/                     # активные задачи
│   │   ├── results/                   # результаты задач
│   │   ├── agents/                    # состояние агентов/ролей
│   │   ├── domains/                   # совет директоров / домены бизнеса
│   │   ├── decisions/                 # решения директоров/оператора
│   │   ├── controls/                  # control checks, gates, policies
│   │   ├── checkpoints/               # resume-points для error recovery
│   │   └── audit/                     # audit trail
│   ├── audit_mailbox/                 # только связь аудиторов
│   ├── internal_contour/              # текущий file-based внутренний контур, постепенно мигрирует в runtime/
│   ├── codex/                         # write-channel tasks/results/proofs
│   ├── reports/                       # operator/audit reports
│   └── state/                         # legacy state до миграции в runtime/
├── agents/                            # runtime contracts and adapters
│   ├── board/                         # domain directors
│   ├── roles/                         # analyst/auditor/executor/monitor
│   └── adapters/                      # github, telegram, crm, accounting
├── scripts/                           # all logic called by workflows
├── .github/workflows/                 # thin workflow entrypoints only
├── products/                          # бизнес-продукты внутри mono-repo на первом этапе
│   ├── shared/
│   └── barber-staff/
│       ├── docs/
│       ├── src/
│       ├── tests/
│       └── governance-link.json
└── integrations/                      # external integrations schemas/connectors
    ├── telegram/
    ├── github/
    ├── accounting/
    └── crm/
```

## Registry, которые нужно создать
| № | Registry | Назначение |
|---|---|---|
| 1 | `governance/runtime/domains/directors.json` | Совет директоров: домены, полномочия, SLA, escalation. |
| 2 | `governance/runtime/agents/agents.json` | Агенты/роли: lifecycle, runner, permissions, health. |
| 3 | `governance/runtime/tasks/*.json` | Активные задачи: trace_id, owner, lane, status, dependencies. |
| 4 | `governance/runtime/results/*.json` | Результаты: immutable evidence, commit, controls, status. |
| 5 | `governance/runtime/controls/policies.json` | Risk-based lanes, blocking criteria, approval thresholds. |
| 6 | `governance/runtime/checkpoints/*.json` | Checkpoint/resume для error recovery. |
| 7 | `governance/runtime/audit/*.jsonl` | Append-only audit trail. |
| 8 | `products/product_registry.json` | Список продуктов, владельцы-директора, repo/path, SLA, status. |

## Стратегия по продуктам
| Вариант | Когда | Плюсы | Минусы |
|---|---|---|---|
| Mono-repo now | текущий этап и первый продукт | проще контроль, единый audit trail, меньше инфраструктуры | при росте может стать тяжёлым |
| Hybrid next | когда появится 2+ продукта или отдельные клиенты | масштабируется, продукты изолированы, управление единое | нужны cross-repo adapters и permissions |
| Multi-repo later | несколько клиентов/SLA/product teams | максимальная изоляция и масштаб | сложнее orchestration, больше DevOps |

## Миграция
| Шаг | Наименование | Результат |
|---|---|---|
| M1 | Repo skeleton | Создать docs/, agents/, products/, governance/runtime/ skeleton with README per folder. |
| M2 | Runtime registry v2 | Ввести схемы tasks/results/agents/domains/controls/checkpoints/audit. |
| M3 | Board registry | Описать директоров доменов, полномочия, escalation, KPI/SLA. |
| M4 | Product registry | Описать продукты и связь продукта с доменами/директорами. |
| M5 | Role-runtime contracts | Контракты analyst/auditor/executor/monitor/board-director. |
| M6 | Role-specific runners | Отдельные runners, но одинаковая схема registry/evidence. |
| M7 | Hybrid split readiness | Подготовить products/* так, чтобы продукт можно было вынести в отдельный repo без потери управления. |

## Найденные текущие документы
- `governance/AGENT_ROLES.md`
- `governance/GPT_ARCHITECTURE_UPDATE.md`
- `governance/INTERNAL_CONTOUR_REFERENCE.md`
- `governance/MASTER_PLAN.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit_v2.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit_v2.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_curator_role_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_curator_role_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit_v2.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit_v2.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem530_internal_contour_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem530_internal_contour_audit_v2.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_curator_role_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_internal_role_contour_audit.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_internal_role_contour_audit_v2.json`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem530_internal_contour_audit_and_roadmap.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_claude_internal_contour_roadmap_update.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_curator_role_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_full_curator_entry_architecture_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_internal_role_contour_audit.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/tasks/pending/BEM530_INTERNAL_CONTOUR_IMPROVEMENT_ROADMAP.md`
- `governance/archive/bem531_00_cleanup_preflight_20260517/governance/tasks/pending/BEM532_REPOSITORY_ARCHIVE_CLEANUP_ROADMAP.md`
- `governance/archive/bem531_3_workflow_audit_20260517/.github/workflows/role-orchestrator.yml`
- `governance/archive/bem532_20260517_phase1/governance/codex/results/bem525_p9_roadmap_update.json`
- `governance/archive/bem532_20260517_phase1/governance/codex/results/bem525_p9_roadmap_update.md`
- `governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem525_p9_roadmap_update.json`
- `governance/archive/bem532_20260517_phase1/governance/tasks/pending/P8_FULL_ROLE_CYCLE_E2E.md`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/auditor_ledger_payload_v3_6_rc2.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/auditor_materialize_result.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/auditor_packet_v3_6_rc2.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/auditor_real_call_request.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/auditor_real_call_response_raw.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/executor_ledger_payload_v3_6_rc2.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/executor_materialize_result.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/executor_packet_v3_6_rc2.json`
- `governance/archive/legacy-2026-05-01/full-repo-cleanup/.runtime/executor_real_call_request.json`

## Blocker
null
