import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.main import load_demo, create_analysis, AnalysisIn, get_analysis
from app.query_parser import parse_query

q = 'Show flooded areas around Assam between July and August 2025.'
parsed = parse_query(q)
assert parsed['intent'] == 'flood_detection'
assert parsed['location']['key'] == 'assam'
assert parsed['date_range']['periods'][0]['label'] == 'July 2025'
assert parsed['date_range']['periods'][1]['label'] == 'August 2025'

samples = load_demo()
assam = sorted([x for x in samples if x['filename'].startswith('Assam_')], key=lambda x: x['metadata'].get('acquired_at') or '')
assert len(assam) == 3  # 2 SAR + 1 overlapping optical
assert assam[0]['metadata']['bounds_wgs84'][0] > 89
assert assam[1]['metadata']['bounds_wgs84'][2] < 97

job = create_analysis(AnalysisIn(query=q, dataset_ids=[x['id'] for x in assam], provider='local'))
for _ in range(120):
    row = get_analysis(job['analysis_id'])
    if row['status'] in ('completed', 'failed'):
        break
    time.sleep(0.05)
print('status:', row['status'])
if row['status'] != 'completed':
    raise SystemExit(json.loads(row['result_json'] or '{}'))
result = json.loads(row['result_json'])
assert result['intent'] == 'flood_detection'
assert 'probable_flood_area_km2' in result['statistics']
assert result['map_context']['bounds_wgs84']
assert len(result['geojson']['features']) > 0
print('answer:', result['answer'])
print('statistics:', result['statistics'])
print('confidence:', result['confidence'], result['confidence_type'])
print('method:', result['method'])
print('geojson features:', len(result['geojson']['features']))
print('SMOKE TEST PASS')
