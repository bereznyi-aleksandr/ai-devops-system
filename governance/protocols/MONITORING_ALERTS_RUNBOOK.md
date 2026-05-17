# BEM-527 | P11 Monitoring + Alerts Runbook

Дата: 2026-05-17 | 11:59 (UTC+3)

## Назначение
Файловый monitoring и alerting для ai-devops-system без issue #31, без schedule triggers, без paid OpenAI API.

## Health checks
1. Deno healthCheck: version must be 4.9 or higher, /codex-task and /codex-status available.
2. codex-runner.yml: ubuntu-latest Python executor, workflow_dispatch only, no schedule.
3. roadmap_state.json: blocker=null, current_phase актуален.
4. governance/codex/results/<trace>.md: completed blocks must have commit_sha.
5. governance/reports/: phase PASS reports exist for closed phases.

## Alert rules
- queued longer than allowed polling window: inspect Actions/result state, do not spam operator.
- failed with blocker: record exact blocker and launch one recovery block.
- completed without target file: mark partial and create blocker report.
- schedule trigger found: critical violation, remove immediately.
- issue #31 comment attempt: critical violation, stop and report.
- paid API/Codex CLI reintroduced: critical violation unless explicitly approved.

## Reporting
Operator receives only closed block report, roadmap closure, or exact blocker. No intermediate dispatch/queued reports.
