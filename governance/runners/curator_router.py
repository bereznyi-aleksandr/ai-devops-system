#!/usr/bin/env python3
from pathlib import Path
import json

OBJECT_PASSPORTS = Path('governance/state/object_passports.json')


def load_passports():
    if not OBJECT_PASSPORTS.exists():
        return []
    return json.loads(OBJECT_PASSPORTS.read_text(encoding='utf-8')).get('objects', [])


def find_object_by_curator(curator_id):
    for obj in load_passports():
        if obj.get('curator_element_id') == curator_id:
            return obj
    return None


def route_vertical(source_curator, target_curator, payload):
    source_obj = find_object_by_curator(source_curator)
    target_obj = find_object_by_curator(target_curator)
    if not source_obj or not target_obj:
        return {'status': 'rejected', 'reason': 'unknown_curator'}
    return {
        'status': 'routed',
        'route_type': 'vertical_curator_to_curator',
        'source_object': source_obj.get('object_id'),
        'target_object': target_obj.get('object_id'),
        'source_curator': source_curator,
        'target_curator': target_curator,
        'payload': payload
    }


def route_to_contour(curator_id, contour_id, payload):
    obj = find_object_by_curator(curator_id)
    if not obj:
        return {'status': 'rejected', 'reason': 'unknown_curator'}
    if contour_id not in obj.get('internal_contours', []):
        return {'status': 'rejected', 'reason': 'contour_not_owned_by_object'}
    return {'status': 'routed', 'route_type': 'contour_input', 'target_role': 'analyst', 'curator': curator_id, 'contour_id': contour_id, 'payload': payload}

if __name__ == '__main__':
    print(json.dumps(route_vertical('EL-CUR-GD-001','EL-CUR-DIR-001', {'task':'selftest'}), ensure_ascii=False))
