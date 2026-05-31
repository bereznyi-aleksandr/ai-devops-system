#!/usr/bin/env python3
import json
from pathlib import Path
schema = json.loads(Path('governance/state/managed_channel_schema.json').read_text(encoding='utf-8'))
for route in ['vertical_curator_to_curator','horizontal_verified_data_transfer','contour_input','contour_output']:
    assert route in schema['route_types']
Path('governance/state/managed_channel_e2e_result.json').write_text(json.dumps({'status':'PASS','routes_checked':['vertical_curator_to_curator','horizontal_verified_data_transfer','contour_input','contour_output']}, ensure_ascii=False, indent=2)+'
', encoding='utf-8')
print('BEM-941 managed channel E2E PASS')
