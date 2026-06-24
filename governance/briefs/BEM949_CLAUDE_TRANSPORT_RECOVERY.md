# BEM-949 — Claude transport persistence recovery brief

## Objective
Produce a bounded, evidence-first plan for making `claude.yml` persist a governed role result reliably without creating invalid GitHub Actions workflow files or losing an executor's intended changes.

## Observed evidence
1. Claude Code run #2706 reached the role-result stage, and the role summary reported `analyst | success`. The job then failed only at `Commit trace report safely` because `git rebase origin/main` was invoked while the workspace still had unstaged files.
2. The current `claude.yml` repair stashes untracked files before rebase, restores them with `git stash pop`, and fails the job if stash restoration conflicts.
3. A previous attempted repair accidentally saved a *step snippet* as `.github/workflows/commit-trace-report-step.yml`. GitHub rejected that file because a workflow file cannot begin with a YAML sequence. A later `jobs: {}` placeholder was also invalid because GitHub requires a runnable root job.
4. The stray file has now been converted into an intentionally inert, manual `noop` workflow. This must remain valid and must not be used as a transport-step fragment.
5. BEM-949 P1 and P4 are upstream-blocked. Do not claim Broad Release PASS. This task is solely a transport/persistence hardening analysis.

## Required analysis
- Inspect the live `claude.yml` persistence step and identify race/conflict cases still possible after the stash-based repair.
- Recommend the smallest code change that preserves all intended role output, does not suppress a failed `stash pop`, and avoids a partial report commit.
- Recommend a deterministic verification procedure using a non-mutating analyst dispatch, including what artifacts prove success.
- Recommend a repository guard that prevents workflow-step fragments or zero-job placeholders from being placed under `.github/workflows/`.
- Do not edit repository files in this role. Write the result as the governed trace report.

## Acceptance criteria for the plan
- Every proposed change names exact target files and deterministic checks.
- The plan distinguishes code validation from runtime evidence.
- The plan preserves the current BEM-949 blocked status for P1/P4.
