# BEM-533 | Telegram Branch Curator Integration Roadmap

Дата: 2026-05-17 | 12:53 (UTC+3)

## Цель
Подключить Telegram bot/webhook branch к уже закрытому внутреннему role-based контуру через curator intake, не нарушая внешний GPT autonomy contour и BEM-531 internal contour PASS.

## Исходная точка
BEM-531 PASS: curator intake, role state, transport contract, workflow audit, synthetic E2E and contour_status.json completed. Telegram был deferred.

## Этапы

### BEM-533.0 — Telegram branch preflight
Проверить существующие Telegram/webhook упоминания, Deno webhook, transport/state compatibility, security constraints.
PASS: preflight report, roadmap, blocker=null.

### BEM-533.1 — Telegram intake schema activation
Перевести Telegram из deferred в active external source в curator intake contract, не добавляя secrets.
PASS: schema updated, sample active Telegram record, blocker=null.

### BEM-533.2 — Telegram transport sample + failure handling
Добавить transport records для telegram_intake, telegram_ack, telegram_failure.
PASS: samples + validator proof.

### BEM-533.3 — Curator Telegram E2E synthetic test
Провести synthetic Telegram input -> curator -> executor -> curator closure без реального Telegram API.
PASS: role state updated, transport records appended, report/proof.

### BEM-533.4 — Contour status update
Обновить contour_status.json: telegram_scope=active_synthetic_verified, external_sources_scope includes telegram.
PASS: status updated, roadmap done, blocker=null.

## Ограничения
- No Telegram token in files.
- No secrets in files.
- No issue #31 comments.
- No schedule triggers.
- No paid OpenAI API.
- Synthetic tests only unless operator explicitly provides live Telegram test instruction.
