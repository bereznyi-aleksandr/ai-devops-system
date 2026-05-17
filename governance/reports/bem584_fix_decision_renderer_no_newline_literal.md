# BEM-584 | Fix Decision Renderer No Newline Literal | PASS

Дата: 2026-05-17 | 22:09 (UTC+3)

Renderer and recorder now use bytes.fromhex("0a") internally; no literal newline string. Valid live-test decision package recreated.

Blocker: null
