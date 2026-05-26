# BEM-866 dispatch error slug
Code: INVALID_REF
Status: DISPATCH_FAILED
Workflow: claude_internal_auditor_dispatcher.yml

Error:
Command 'gh workflow run claude_internal_auditor_dispatcher.yml --ref main -f trace_id=bem865_claude_write_selftest -f task_path=governance/tasks/pending/CLAUDE_WRITE_SELFTEST_BEM865.md -f response_path=governance/audit/mailbox/from_claude/BEM865_CLAUDE_WRITE_SELFTEST_RESPONSE.md -f expected_status=CLAUDE_WRITE_OK' returned non-zero exit status 1.
