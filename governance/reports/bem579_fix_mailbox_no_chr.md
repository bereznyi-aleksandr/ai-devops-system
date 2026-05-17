# BEM-579 | Fix Mailbox Dispatcher No chr | PASS

Дата: 2026-05-17 | 21:56 (UTC+3)

## Result
Mailbox dispatcher scripts rewritten without executor `chr()` usage. Generated scripts use internal `NL` variable. Routine mailbox Telegram remains disabled; operator decisions are handled only by structured decision queue.

## Blocker
null
