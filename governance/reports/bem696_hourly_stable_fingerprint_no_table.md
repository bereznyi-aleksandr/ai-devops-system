# BEM-696 | Hourly Stable Fingerprint No Table | FAILED

Дата: 2026-05-19 | 10:13 (UTC+3)

No-change теперь определяется только по стабильному fingerprint статусов, а не по служебным полям snapshot.

Blocker: {"code": "STABLE_FINGERPRINT_PATCH_FAILED", "failed": [{"name": "stable_fingerprint_present", "pass": false, "evidence": "scripts/render_curator_hourly_report.py"}, {"name": "snapshot_stores_fingerprint", "pass": false, "evidence": "scripts/render_curator_hourly_report.py"}]}
