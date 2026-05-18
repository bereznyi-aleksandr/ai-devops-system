# BEM-609 | YAML And Commit Failure Hardening

Дата: 2026-05-18 | 06:24 (UTC+3)

## Fixed
- Claude provider gate no longer embeds JSON heredoc in YAML.
- Provider gate uses Python script.
- Router workflows commit before pull/rebase and use autostash-safe pull/push.
- Dispatcher/router workflows still avoid committing shared transport results to reduce conflicts.
