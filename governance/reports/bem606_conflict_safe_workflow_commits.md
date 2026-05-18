# BEM-606 | Conflict-Safe Workflow Commits | PASS

Дата: 2026-05-18 | 06:13 (UTC+3)

Updated autonomous dispatcher/router workflows so they do not commit shared `governance/transport/results.jsonl`. This removes the merge-conflict source shown in GitHub Actions screenshots.

## Changed workflows

- .github/workflows/mailbox-dispatcher.yml
- .github/workflows/operator-decision-dispatcher.yml
- .github/workflows/operator-reply-intake.yml
- .github/workflows/decision-curator-handoff.yml
- .github/workflows/curator-inbox-router.yml
- .github/workflows/role-orchestrator-internal-router.yml

## Blocker
null
