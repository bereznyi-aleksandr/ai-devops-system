# BEM-635 | Telegram Delivery Proof Layers

Дата: 2026-05-18 | 07:47 (UTC+3)

Delivery proof has two layers:
1. Direct smoke: checks bot token/chat delivery without hourly renderer.
2. Hourly renderer delivery: checks canonical report workflow.

If direct smoke passes but hourly delivery fails, the blocker is renderer/workflow. If direct smoke fails, the blocker is Telegram credentials/chat/network.
