# AGENT_CONTEXT.md | canonical configuration

Updated: 2026-06-18T13:51:17Z
Repository: bereznyi-aleksandr/ai-devops-system
Active protocol: BEM-934
Roadmap state: 9/10 stages complete
Current task: BEM934-CLOSE
Release status: FOLLOW_UP_REQUIRED

## Operational provider architecture

Primary provider for curator, analyst, auditor, and executor: `claude_code`.
Primary workflow: `.github/workflows/claude.yml`.
Operational ingress: Telegram -> Cloudflare Worker -> `provider-router.yml` -> `claude.yml`.

Historical self-hosted Codex paths are disabled and deprecated. They are not an available operational runtime.
`gpt_codex_cloud` is a GitHub-hosted reserve path. It may claim LLM execution only when OpenAI runtime secrets are configured; otherwise it is a clearly labelled `mechanical_fallback`.

## Verified BEM-934 state

Stages 1-8: DONE.
Stage 9 `BEM934-LIVE-TEST`: DONE under strict receipt v2.
Operator trace: `;tg_818730867_20260618T105741Z`.
Provider route: `claude_code` -> `claude.yml`.
Semantic executor transport: `completed`, blocker `null`.
Historical failed attempts remain disclosed.
The prior replay-based contradictory PASS is archived as superseded.

Stage 10 `BEM934-CLOSE`: IN_PROGRESS.
Closure is not approved yet. Release remains `FOLLOW_UP_REQUIRED` until an independent `EXTERNAL_AUDITOR_CLAUDE verdict is PASS/APPROVED and a strict final validator succeeds.

## Canonical evidence

- `governance/proofs/BEM934_live_test_receipt.json`
- `governance/proofs/BEM934_live_test_receipt_superseded_replay.json`
- `governance/roadmap/ACTIVE_QUEUE.json`
- `governance/config/provider_config.json`
- `governance/protocols/BEM934_Protocol.md`

## Closure rule

No top-level PASS may contradict nested transport records. No replay may be represented as operator-authored ingress. Release PASS requires committed proof files, independent external Claude approval, and a final fail-closed validator.
