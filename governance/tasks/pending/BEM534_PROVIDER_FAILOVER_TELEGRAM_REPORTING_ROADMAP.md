# BEM-534 | Provider Failover + Telegram Reporting Roadmap

Дата: 2026-05-17 | 12:59 (UTC+3)

## Цель
Проверить и доработать основной/резервный контуры provider failover и Telegram reporting по канону.

## Этапы

### BEM-534.1 — Provider failover contract
Формализовать primary Claude contour и reserve GPT contour: состояние лимитов, критерий переключения, запись решения curator/provider-adapter в transport/state.
PASS: protocol, samples, state fields, no secrets.

### BEM-534.2 — Provider adapter failover implementation
Доработать provider-adapter.yml или file-based adapter protocol так, чтобы при Claude unavailable/limit_exceeded route переходил на GPT reserve contour.
PASS: synthetic test Claude unavailable -> GPT reserve selected.

### BEM-534.3 — Main/reserve contour E2E
Провести synthetic E2E: primary available, primary limit exceeded, reserve selected, final result recorded.
PASS: transport records, role state, report, blocker=null.

### BEM-534.4 — Telegram canonical report delivery contract
Формализовать отправку канонического отчёта в Telegram. Важно: schedule triggers запрещены, поэтому hourly delivery нельзя делать через GitHub schedule. Нужно определить разрешённый источник часового тика: Deno runtime/timer, external uptime monitor, manual operator trigger или другой явно разрешённый механизм.
PASS: protocol and no secret storage.

### BEM-534.5 — Telegram reporting synthetic test
Провести synthetic test генерации canonical report payload для Telegram без live secret.
PASS: sample payload, transport record, no secret in files, blocker=null.
