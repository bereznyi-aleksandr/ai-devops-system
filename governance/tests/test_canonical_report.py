#!/usr/bin/env python3
from pathlib import Path
template = Path('governance/reports/templates/canonical_report_template.md')
if not template.exists():
    raise SystemExit('MISSING canonical report template')
text = template.read_text(encoding='utf-8')
for token in ['Этап:', 'Дорожная карта:', 'Чек-лист:', 'Proof:', 'Следующее действие']:
    if token not in text:
        raise SystemExit('MISSING token: ' + token)
Path('governance/state/canonical_report_test_result.json').write_text('{"status":"PASS"}
', encoding='utf-8')
print('BEM-941 canonical report test PASS')
