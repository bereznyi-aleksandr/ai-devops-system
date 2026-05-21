# BEM-739 | Repair Lint Gate After Claude Bridge | LINT_GATE_STILL_HAS_NEW_VIOLATIONS

Дата: 2026-05-21 | 14:33 (UTC+3)

New lint violations: 2

Blocker: {"code": "NEW_WORKFLOW_LINT_VIOLATIONS_REMAIN", "count": 2, "new": [{"file": ".github/workflows/claude-internal-auditor-dispatcher.yml", "line": 32, "rule": "NO_INLINE_CODE", "text": "python3 - <<'PY' > /tmp/active.txt"}, {"file": ".github/workflows/claude-internal-auditor-dispatcher.yml", "line": 32, "rule": "NO_INLINE_HEREDOC", "text": "python3 - <<'PY' > /tmp/active.txt"}]}
