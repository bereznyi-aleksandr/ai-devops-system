# BEM-535 | Report for Claude — Provider Contours, Limits, GPT Scheduler and Telegram Reporting

Дата: 2026-05-17 | 13:02 (UTC+3)

## 1. Ответ на замечания оператора

| Наименование | Описание | Обоснование |
|---|---|---|
| Provider contours | Да, схема должна учитывать основной Claude contour и резервный GPT contour | Оператор указал на необходимость переключения при лимитах Claude |
| Failover status | До BEM-535 полноценный E2E main/reserve не был доказан | BEM-531/BEM-533 проверяли role contour и Telegram synthetic branch, но не provider-limit switching |
| Curator | Curator трактуется как GPT Codex / GPT control layer | Оператор уточнил, что curator связан с GPT Codex и может использовать внутренний Scheduler |
| Analyst | Analyst должен быть явно закреплён как GPT Codex | Оператор указал: обязательный аналитик — GPT Codex |
| Telegram hourly reporting | Нужно учитывать отправку канонического отчёта в Telegram раз в час через внутренний GPT Scheduler | Это не GitHub Actions schedule; запрет schedule triggers остаётся для workflows |
| Current state | Provider failover и hourly Telegram report пока не PASS | Нужна отдельная BEM-535 roadmap |

## 2. Что уже сделано GPT по предыдущей roadmap

| Наименование | Описание | Обоснование |
|---|---|---|
| BEM-531.00 Cleanup preflight | Архивация устаревших planning/audit artifacts и проверка активных контуров | SHA fed8d7d0854a3055959e287638422dfc4eeae597 |
| BEM-531.01 Curator intake | Curator intake contract, FSM and samples | SHA b26ddc22d7f20e507aec67484735a7f2fc7cca0c |
| BEM-531.1 Role state + lifecycle | role_cycle_state normalized, CANDIDATE -> ACTIVE -> RETIRED lifecycle | SHA 5d26e973ed67f61dca308db081d745e044d431f5 |
| BEM-531.2 Transport + failure handling | File transport contract and failure records | SHA b464c7f5c5f5a05b354218c6194263e7d46a41b9 |
| BEM-531.3 Workflow audit | role-orchestrator/provider-adapter normalized to workflow_dispatch/no schedule | SHA 82ced4dbdc37890c97ee4522aae77b525cb8b184 |
| BEM-531.4 Synthetic E2E | Minimal and full role-cycle E2E completed | SHA 9005e6c1bf5e87a0c77df2734f23806902419269 |
| BEM-531.5 Contour status | contour_status.json created and BEM-531 closed | SHA 5ecf72493da8135a1a6762b2bce9f2d09b3b909b |
| BEM-533 Telegram synthetic branch | Telegram branch activated synthetically through curator | Final SHA b4b28d6c588789aec97d89d14ecffc382b944186 |

## 3. Audit observations

| Наименование | Описание | Обоснование |
|---|---|---|
| Existing workflow checks | See JSON below | Repository scan performed by Run script |
| Provider failover confirmed | False | Must be implemented/tested in BEM-535 |
| Telegram hourly confirmed | True | Must be formalized via GPT Scheduler contract and synthetic payload test |
| GitHub schedule policy | GitHub schedule remains prohibited | Contract forbids workflow schedule triggers; Scheduler is GPT-internal, not workflow schedule |

```json
[
  {
    "file": ".github/workflows/provider-adapter.yml",
    "exists": true,
    "workflow_dispatch": true,
    "schedule_trigger": false,
    "claude_present": false,
    "gpt_present": false,
    "codex_present": false,
    "failover_present": false,
    "telegram_present": false,
    "limit_present": false
  },
  {
    "file": ".github/workflows/role-orchestrator.yml",
    "exists": true,
    "workflow_dispatch": true,
    "schedule_trigger": false,
    "claude_present": true,
    "gpt_present": true,
    "codex_present": false,
    "failover_present": false,
    "telegram_present": true,
    "limit_present": false
  },
  {
    "file": ".github/workflows/codex-runner.yml",
    "exists": true,
    "workflow_dispatch": true,
    "schedule_trigger": false,
    "claude_present": false,
    "gpt_present": false,
    "codex_present": true,
    "failover_present": false,
    "telegram_present": false,
    "limit_present": false
  }
]
```

## 4. Proposed BEM-535 roadmap for external audit approval

| Этап | Название | Описание | Обоснование |
|---|---|---|---|
| 1 | BEM-535.1 Provider contour architecture contract | Primary Claude contour, reserve GPT contour, Curator=GPT Codex, Analyst=GPT Codex, switch reasons | Need explicit architecture before implementation |
| 2 | BEM-535.2 Provider limit state + decision matrix | provider_contour_state.json with statuses, limits, last switch, history | Limit control must be stateful and auditable |
| 3 | BEM-535.3 Provider adapter failover implementation | If Claude unavailable/limit_exceeded -> choose GPT reserve | Main functional missing piece |
| 4 | BEM-535.4 Synthetic failover E2E | Test Claude available and Claude limit_exceeded -> GPT reserve | PASS requires proof, not assumption |
| 5 | BEM-535.5 GPT Scheduler hourly Telegram report contract | Canonical hourly report via GPT Scheduler, not GitHub schedule | Operator clarified GPT has internal scheduler capability |
| 6 | BEM-535.6 Telegram hourly reporting synthetic test | Generate canonical Telegram report payload without live token | No secrets in repo, synthetic first |
| 7 | BEM-535.7 Final contour status update | Update contour_status.json and close roadmap | Make state machine-readable |

## 5. Relevant repository hits
- .github/workflows/actions-diagnostic.yml: terms=codex,limit, bytes=5438
- .github/workflows/analyst.yml: terms=claude,analyst,аналитик, bytes=1230
- .github/workflows/auditor.yml: terms=claude,analyst, bytes=1249
- .github/workflows/claude.yml: terms=provider,claude,curator,analyst,limit, bytes=15034
- .github/workflows/cloud-scheduler-tick.yml: terms=scheduler,schedule, bytes=136
- .github/workflows/codex-local.yml: terms=provider,gpt,codex,curator,analyst,limit,primary, bytes=12612
- .github/workflows/codex-runner.yml: terms=codex, bytes=23895
- .github/workflows/curator-hosted-gpt.yml: terms=provider,fallback,claude,gpt,curator,analyst,limit,telegram, bytes=12755
- .github/workflows/curator-hourly-report.yml: terms=curator,analyst,telegram,hourly,schedule, bytes=4433
- .github/workflows/curator-monitor.yml: terms=claude,gpt,codex,curator,куратор, bytes=241
- .github/workflows/curator-telegram-report.yml: terms=curator,telegram, bytes=136
- .github/workflows/curator.yml: terms=fallback,claude,gpt,codex,curator,analyst,telegram, bytes=9641
- .github/workflows/executor.yml: terms=claude, bytes=1251
- .github/workflows/fix-telegram-webhook.yml: terms=telegram, bytes=165
- .github/workflows/gpt-action-ingress.yml: terms=gpt, bytes=4634
- .github/workflows/gpt-curator-inbox.yml: terms=gpt,curator, bytes=136
- .github/workflows/gpt-dev-entrypoint.yml: terms=gpt,contour, bytes=6470
- .github/workflows/gpt-dev-runner.yml: terms=gpt,contour, bytes=8621
- .github/workflows/gpt-hosted-roles.yml: terms=provider,claude,gpt,codex,curator,analyst,limit, bytes=14973
- .github/workflows/gpt-scheduler-tick.yml: terms=gpt,scheduler,schedule, bytes=136
- .github/workflows/provider-adapter.yml: terms=provider,curator,analyst, bytes=2199
- .github/workflows/role-orchestrator.yml: terms=claude,gpt,curator,analyst,telegram, bytes=2486
- .github/workflows/role-router.yml: terms=provider,reserve,claude,gpt,curator,analyst,limit, bytes=4421
- .github/workflows/system-status-report.yml: terms=schedule, bytes=2661
- .github/workflows/telegram-gateway.yml: terms=curator,telegram, bytes=263
- .github/workflows/telegram-outbox-dispatch.yml: terms=telegram,schedule, bytes=4318
- .github/workflows/telegram-poll.yml: terms=telegram, bytes=136
- .github/workflows/telegram-report.yml: terms=telegram, bytes=170
- .github/workflows/telegram-send.yml: terms=telegram, bytes=170
- .github/workflows/telegram-webhook.yml: terms=telegram, bytes=170
- governance/AGENT_ROLES.md: terms=claude,gpt,analyst,куратор, bytes=1467
- governance/AUDIT_DIFF_PROTOCOL.md: terms=claude,gpt, bytes=2787
- governance/AUTONOMOUS_CURATOR_PROTOCOL.md: terms=curator, bytes=281
- governance/CURATOR_CONTRACT.md: terms=provider,claude,gpt,codex,curator,analyst,аналитик,куратор,telegram,schedule,contour, bytes=4920
- governance/EXCHANGE.md: terms=telegram, bytes=607
- governance/EXTERNAL_AUDITOR_CONTRACT.md: terms=claude,gpt,curator,куратор, bytes=3520
- governance/GPT_ARCHITECTURE_UPDATE.md: terms=gpt, bytes=11
- governance/GPT_CURATOR_AUTONOMOUS_GUIDE.md: terms=gpt,curator, bytes=132
- governance/GPT_CUSTOM_INSTRUCTIONS.md: terms=provider,claude,gpt,codex,curator,analyst,куратор,telegram,schedule,contour, bytes=5171
- governance/GPT_HANDOFF.md: terms=provider,failover,claude,gpt,codex,лимит,schedule,contour, bytes=4039
- governance/GPT_NEW_START.md: terms=gpt, bytes=7
- governance/GPT_REPORTING_CONTRACT.md: terms=gpt, bytes=45
- governance/GPT_WRITE_CHANNEL.md: terms=gpt,codex,limit, bytes=5653
- governance/INTERNAL_CONTOUR_REFERENCE.md: terms=provider,fallback,backup,claude,gpt,curator,limit,telegram,schedule,contour,primary, bytes=7525
- governance/MASTER_PLAN.md: terms=fallback,claude,gpt,codex,curator,analyst,аналитик,куратор,limit,scheduler,schedule,contour,primary, bytes=4223
- governance/NO_MANUAL_CONFIRMATION.md: terms=gpt,curator,analyst,куратор,telegram, bytes=1722
- governance/SCHEDULER_PROTOCOL.md: terms=scheduler,schedule, bytes=45
- governance/TELEGRAM_INTERFACE_TASK.md: terms=telegram, bytes=45
- governance/TELEGRAM_STATUS.md: terms=telegram, bytes=45
- governance/archive/bem531_00_cleanup_preflight_20260517/MANIFEST.md: terms=claude,codex,curator,schedule,contour, bytes=9615
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem530_internal_contour_audit.txt: terms=codex,contour, bytes=213
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem530_internal_contour_audit_v2.txt: terms=codex,contour, bytes=482
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem531_add_cleanup_first_task.txt: terms=claude,codex,contour, bytes=479
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem531_curator_role_audit.txt: terms=codex,curator,contour, bytes=415
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem531_full_curator_entry_audit.txt: terms=codex,curator,contour, bytes=463
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem531_internal_role_contour_audit.txt: terms=codex,contour, bytes=216
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/proofs/bem531_internal_role_contour_audit_v2.txt: terms=codex,contour, bytes=453
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit.json: terms=codex,contour, bytes=528
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit.md: terms=codex,contour, bytes=497
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit_v2.json: terms=codex,contour, bytes=792
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem530_internal_contour_audit_v2.md: terms=codex,contour, bytes=728
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_add_cleanup_first_task.json: terms=claude,codex,contour, bytes=782
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_add_cleanup_first_task.md: terms=claude,codex,contour, bytes=718
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_curator_role_audit.json: terms=codex,curator,contour, bytes=711
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_curator_role_audit.md: terms=codex,curator,contour, bytes=647
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_full_curator_entry_audit.json: terms=codex,curator,contour, bytes=771
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_full_curator_entry_audit.md: terms=codex,curator,contour, bytes=707
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit.json: terms=codex,contour, bytes=541
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit.md: terms=codex,contour, bytes=510
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit_v2.json: terms=codex,contour, bytes=773
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/results/bem531_internal_role_contour_audit_v2.md: terms=codex,contour, bytes=709
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem530_internal_contour_audit.json: terms=provider,claude,gpt,codex,analyst,schedule,contour, bytes=9656
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem530_internal_contour_audit_v2.json: terms=provider,claude,gpt,codex,analyst,schedule,contour, bytes=8181
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_add_cleanup_first_task.json: terms=provider,claude,gpt,codex,curator,analyst,schedule,contour, bytes=5973
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_curator_role_audit.json: terms=provider,gpt,codex,curator,analyst,куратор,telegram,schedule,contour, bytes=5450
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_full_curator_entry_audit.json: terms=provider,claude,gpt,codex,curator,analyst,аналитик,куратор,telegram,schedule,contour, bytes=6519
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_internal_role_contour_audit.json: terms=provider,gpt,codex,analyst,аналитик,schedule,contour, bytes=9671
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/codex/tasks/bem531_internal_role_contour_audit_v2.json: terms=provider,gpt,codex,analyst,аналитик,schedule,contour, bytes=9490
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem530_internal_contour_audit_and_roadmap.md: terms=provider,claude,gpt,codex,curator,analyst,telegram,hourly,scheduler,schedule,contour, bytes=5572
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_claude_internal_contour_roadmap_update.md: terms=provider,claude,gpt,codex,curator,analyst,schedule,contour, bytes=1765
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_curator_role_audit.md: terms=provider,gpt,codex,curator,analyst,contour, bytes=1825
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_full_curator_entry_architecture_audit.md: terms=provider,claude,gpt,codex,curator,analyst,telegram,contour, bytes=3080
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_internal_role_contour_audit.md: terms=provider,gpt,codex,analyst,schedule,contour, bytes=2606
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/tasks/pending/BEM530_INTERNAL_CONTOUR_IMPROVEMENT_ROADMAP.md: terms=gpt,codex,analyst,schedule,contour, bytes=2026
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/tasks/pending/BEM532_REPOSITORY_ARCHIVE_CLEANUP_ROADMAP.md: terms=codex,curator,schedule,contour, bytes=954
- governance/archive/bem531_3_workflow_audit_20260517/.github/workflows/provider-adapter.yml: terms=provider,claude,gpt,curator,analyst, bytes=12136
- governance/archive/bem531_3_workflow_audit_20260517/.github/workflows/role-orchestrator.yml: terms=provider,claude,analyst,schedule, bytes=6188
- governance/archive/bem532_20260517_phase1/MANIFEST.md: terms=claude,codex,contour, bytes=9236
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem522_fix_runner.txt: terms=reserve,codex, bytes=548
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem522_gcloud_selftest.txt: terms=codex, bytes=60
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem522_workflow_diag.txt: terms=codex, bytes=455
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem524_p8_close_v3_short.txt: terms=codex, bytes=170
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem524_p8_pending_cleanup.txt: terms=codex, bytes=300
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem525_p9_roadmap_update.txt: terms=codex, bytes=170
- governance/archive/bem532_20260517_phase1/governance/codex/proofs/bem526_p10_baseline_audit.txt: terms=codex, bytes=200
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_fix_runner.json: terms=codex, bytes=388
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_fix_runner.md: terms=codex, bytes=585
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_gcloud_selftest.json: terms=codex, bytes=461
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_gcloud_selftest.md: terms=codex, bytes=657
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_patch2_selftest.json: terms=codex, bytes=922
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_patch2_selftest.md: terms=codex, bytes=1080
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_patch3_selftest.json: terms=codex, bytes=922
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_patch3_selftest.md: terms=codex, bytes=1111
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_real_selftest.json: terms=codex, bytes=391
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_real_selftest.md: terms=codex, bytes=524
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_secret_refresh_selftest.json: terms=codex,quota, bytes=937
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_secret_refresh_selftest.md: terms=codex,quota, bytes=1126
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_workflow_diag.json: terms=codex, bytes=397
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem522_workflow_diag.md: terms=codex, bytes=597
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem524_p8_close_v3_short.json: terms=codex, bytes=427
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem524_p8_close_v3_short.md: terms=codex, bytes=401
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem524_p8_pending_cleanup.json: terms=codex, bytes=413
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem524_p8_pending_cleanup.md: terms=codex, bytes=370
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem525_p9_roadmap_update.json: terms=codex, bytes=427
- governance/archive/bem532_20260517_phase1/governance/codex/results/bem525_p9_roadmap_update.md: terms=codex, bytes=401
- governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem522_fix_runner.json: terms=reserve,gpt,codex,schedule,contour, bytes=1003
- governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem522_gcloud_selftest.json: terms=gpt,codex,schedule,contour, bytes=751
- governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem522_patch2_selftest.json: terms=gpt,codex,schedule,contour, bytes=751
- governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem522_patch3_selftest.json: terms=gpt,codex,schedule,contour, bytes=746
- governance/archive/bem532_20260517_phase1/governance/codex/tasks/bem522_real_selftest.json: terms=gpt,codex,schedule,contour, bytes=750

## 6. Blocker
null for report/roadmap preparation. Provider failover and Telegram hourly reporting are pending BEM-535 execution.
