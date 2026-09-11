from __future__ import annotations
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app.main as main
from app.main import AnalysisIn

samples = main.load_demo()
assam = sorted([x for x in samples if x['filename'].startswith('Assam_')], key=lambda x: x['metadata'].get('acquired_at') or '')
job = main.create_analysis(AnalysisIn(query='Show flooded areas around Assam between July and August 2025.', dataset_ids=[x['id'] for x in assam], provider='local'))
for _ in range(300):
    row = main.get_analysis(job['analysis_id'])
    if row['status'] in ('completed','failed'):
        break
    time.sleep(.03)
assert row['status'] == 'completed', row['result_json']
r = json.loads(row['result_json'])
assert r['provenance']['sources'] and len(r['provenance']['sources']) == 2
assert 'confidence_breakdown' in r
assert r['confidence_breakdown']['model_backed'] == r['provenance']['model_backed']
assert 0 <= r['confidence'] <= 1
assert r['confidence_breakdown']['note'].lower().find('not calibrated') >= 0
print('TRUST CONTRACT PASS')
print('model:', r['provenance']['model_display'])
print('fallback:', r['provenance']['fallback_used'])
print('confidence breakdown:', r['confidence_breakdown'])
