# BEM-931 v3.4 | Runtime Update and Claude Review Notes

Updated: 2026-06-07
Status: protocol delta
Source: Operator directive + Claude review of BEM-931 v3.3

## 1. Claude verdict

```text
APPROVED_WITH_NOTES
```

Protocol v3.3 is accepted. Notes are non-blocking but must be reflected in roadmap and implementation order.

## 2. Accepted Claude notes

| ID | Note | Decision |
|---|---|---|
| ZM-1 | RM-05 prompts depend on RM-02..RM-04 | ACCEPTED. ACTIVE_QUEUE must preserve dependency order. |
| ZM-2 | Cross-validation required between elements_registry and element_prompt_profiles | ACCEPTED. Add validation task. |
| ZM-3 | Horizontal-link trigger is not defined | ACCEPTED. RM-07 must define who initiates horizontal link. |
| ZM-4 | RM-12 Minimal Loop depends on all previous tasks | ACCEPTED. RM-12 cannot run before previous roadmap tasks. |
| ZM-5 | Add rule_version to rule_registry | ACCEPTED. Prevent stale rule cache usage. |

## 3. Runtime change

Previous curator runtime:

```text
telegram-poll.yml
-> gpt-hosted-roles.yml
-> OpenAI/Gemini HTTP API
-> paid API usage
```

Canonical curator runtime:

```text
telegram-poll.yml
-> codex-local.yml
-> self-hosted runner [codex-local]
-> Codex CLI
-> ChatGPT OAuth / GPT Plus
-> governance/telegram_outbox.jsonl
-> telegram-outbox-dispatch.yml
-> Telegram operator
```

## 4. Decision

Paid hosted LLM runtimes are deprecated for the normal curator path.

Deprecated:

- Gemini API curator path;
- OpenAI HTTP API curator path;
- `gpt-hosted-roles.yml` as active runtime;
- any mock/skeleton PASS as Release PASS.

Required:

- curator uses `codex-local.yml`;
- curator output to operator remains multiline plaintext;
- checklist items must stay on separate lines;
- external audit mailbox flow remains initiator-sensitive.

## 5. New archive task

Add task:

```text
BEM-931-ARCHIVE-LEGACY-RUNTIMES
```

Goal:

Archive inactive, obsolete, paid API and Gemini workflow branches so they do not interfere with canonical operation.

Acceptance:

- find workflows that use Gemini/OpenAI HTTP API/hosted paid runtime;
- disable automatic triggers for obsolete workflows;
- mark emergency-only workflows explicitly as ARCHIVED/DEPRECATED;
- keep canonical runtime documented as `codex-local.yml`.
