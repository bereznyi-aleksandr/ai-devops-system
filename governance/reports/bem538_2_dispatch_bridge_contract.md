# BEM-538.2 | Dispatch Bridge Contract | PASS

Дата: 2026-05-17 | 13:43 (UTC+3)

## Inspection
| Наименование | Описание | Обоснование |
|---|---|---|
| codex-runner contents write | True | Needed for repo writes |
| codex-runner actions write | False | Needed for nested workflow_dispatch via GITHUB_TOKEN |
| role-orchestrator dispatch ready | True | Target workflow must accept dispatch |
| provider-adapter dispatch ready | True | Target workflow must accept dispatch |
| Bridge mode | needs_codex_runner_actions_write_permission | Derived from workflow permissions |

## Blocker
WORKFLOW_DISPATCH_BRIDGE_NEEDS_ACTIONS_WRITE before real nested dispatch
