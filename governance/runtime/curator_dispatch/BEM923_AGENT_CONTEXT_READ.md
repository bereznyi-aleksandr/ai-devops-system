# BEM-923 AGENT_CONTEXT read
Status: READ
Context exists: True

Key lines:
`roadmap_state.json`, `GPT_HANDOFF.md` и другие state-файлы могут быть устаревшими.
| Deno webhook | ✅ v4.9 LIVE | /codex-task + /codex-status |
| codex-runner.yml | ✅ Работает | ubuntu-latest, Python v3, BEM-849 git push fix |
| GitHub MCP (Claude) | ✅ Работает | прямой write без посредника |
| claude-code-action@v1 | ⚠️ NOT PROVEN | нужен отдельный smoke-test |
- BEM-849: исправлен git push в codex-runner (был double-commit без push)
- BEM-850: исправлен claude-internal-auditor-dispatcher (невалидный with: параметр)
- BEM-858: протокол GPT↔Claude согласован (AGREED)
- claude-code-action@v1 smoke-test (нужен один запуск из UI)
## 3. Согласованный протокол GPT↔Claude (BEM-858)
| GPT и Claude — peer-аудиторы | ✅ APPROVED |
| trace_id | bem849_push_fix_test | Задача в codex-runner через Deno |
| task_id | P9_HANDOFF_PROTOCOL | Запись в roadmap_state.json |
- `governance/codex/results/` — результаты codex-runner
❌ Платные API (Codex CLI, OPENAI_API_KEY)
❌ Останавливать roadmap ради отчёта
GPT Custom → createCodexTask (Deno)
  → Deno /codex-task
    → GitHub Actions codex-runner.yml (ubuntu-latest)
  → getCodexStatus → completed + SHA
Claude → прямой коммит через GitHub MCP
  → governance/audit_mailbox/claude_to_gpt/
| Область | Claude | GPT |
| Аудит | Аудирует GPT | Аудирует Claude |
| State / roadmap | Аудит | Ведение файлов |
2. **claude-code-action smoke-test** — запустить из Actions UI
*Источник истины: этот файл главнее roadmap_state.json и GPT_HANDOFF.md*
## BEM-863 Curator-Claude mechanism
## BEM-864 Curator-Claude selftest
- Status: route_selftest_completed_waiting_for_claude_response
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT.md
Roadmap protocol agreed through curator-mediated route
Updated BEM-872 roadmap protocol to version v1
Updated BEM-872 roadmap protocol to version v1
Dispatch contour implemented after BEM-889 READY baseline
Worker contour inbox delivery implemented
Worker contour task processing implemented
Final sending contour readiness completed
Final autonomous sending contour readiness completed
Roadmap v1
Operator gate reached after maximum autonomous execution of accepted roadmap v1
Prepared detailed external audit report for Claude about protocol v1
Claude external audit remediation validation completed
Prepared system improvement protocol after Claude external audit and BEM-907
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working operational system
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working system, using existing Telegram/Deno/Codex implementation and Claude v1
Updated the BEM-918 working roadmap after operator remarks about the seven listed mechanisms/components and Telegram entry/exit route
Prepared new system evolution protocol after Claude APPROVED_WITH_REQUIREMENTS for BEM-919 and operator request to separately list existing/new object and element prompts for approval
## BEM-921 completed | 2026-05-30
Corrected BEM-920 after operator pointed out that prompt names were listed without readable prompt contents and without explaining how the protocol evolves the raw repository into a working managing contour
## BEM-921 completed | 2026-05-30
Prepared System Working Protocol v2 after operator clarified the correct internal contour algorithm and all 2026-05-30 remarks
## BEM-921 completed | 2026-05-30
Prepared new full-system protocol v2 after today's operator decisions about internal contour algorithm, workspaces, curators, rule inheritance, vertical/horizontal links, GitHub Actions/
