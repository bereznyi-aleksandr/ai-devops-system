# BEM-948 P0 YAML validation failure log

Target run id: `27867354184`
Log retrieval exit code: `0`

## Sanitized targeted excerpt

- `validate	Commit validation evidence	﻿2026-06-20T09:43:03.8486349Z ##[group]Run set -euo pipefail`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8486713Z ^[[36;1mset -euo pipefail^[[0m`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8487004Z ^[[36;1mgit config user.name "BEM-948 Validator"^[[0m`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8487401Z ^[[36;1mgit config user.email "bem948-validator@ai-devops-system"^[[0m`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8488066Z ^[[36;1mgit add governance/proofs/BEM948_claude_yaml_validation_receipt.json governance/reports/bem948_p0_claude_yaml_validation.md^[[0m`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8488900Z ^[[36;1mgit diff --cached --quiet || (git commit -m "BEM-948: validate Claude YAML after turn-budget repair" && git push)^[[0m`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8523611Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {0}`
- `validate	Commit validation evidence	2026-06-20T09:43:03.8523994Z ##[endgroup]`
- `validate	Commit validation evidence	2026-06-20T09:43:03.9847070Z [main a9685eb3] BEM-948: validate Claude YAML after turn-budget repair`
- `validate	Commit validation evidence	2026-06-20T09:43:03.9847863Z  2 files changed, 19 insertions(+)`
- `validate	Commit validation evidence	2026-06-20T09:43:03.9848922Z  create mode 100644 governance/proofs/BEM948_claude_yaml_validation_receipt.json`
- `validate	Commit validation evidence	2026-06-20T09:43:03.9849794Z  create mode 100644 governance/reports/bem948_p0_claude_yaml_validation.md`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2892657Z To https://github.com/bereznyi-aleksandr/ai-devops-system`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2893411Z  ! [rejected]          main -> main (fetch first)`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2894240Z error: failed to push some refs to 'https://github.com/bereznyi-aleksandr/ai-devops-system'`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2905667Z hint: Updates were rejected because the remote contains work that you do not`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2906222Z hint: have locally. This is usually caused by another repository pushing to`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2906709Z hint: the same ref. If you want to integrate the remote changes, use`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2907082Z hint: 'git pull' before pushing again.`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2907468Z hint: See the 'Note about fast-forwards' in 'git push --help' for details.`
- `validate	Commit validation evidence	2026-06-20T09:43:04.2925859Z ##[error]Process completed with exit code 1.`
