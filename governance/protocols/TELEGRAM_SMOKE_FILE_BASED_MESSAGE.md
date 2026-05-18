# BEM-664 | Telegram Smoke File-Based Message

Дата: 2026-05-18 | 15:59 (UTC+3)

Telegram smoke workflow sends a pre-rendered message file with curl `text@file`. This avoids YAML breakage from heredoc and inline multiline shell strings.
