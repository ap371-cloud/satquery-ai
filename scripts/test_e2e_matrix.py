from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app.main as main
from app.main import AnalysisIn


def wait(aid: str, timeout=12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = main.get_analysis(aid)
        if row['status'] in ('completed', 'failed'):
            result = json.loads(row['result_json'] or '{}')
            if row['status'] != 'completed':
                raise AssertionError(f"analysis failed: {result}")
            return result
        time.sleep(0.05)
    raise TimeoutError(aid)


def run(query, ids):
    job = main.create_analysis(AnalysisIn(query=query, dataset_ids=ids, provider='local'))
    return wait(job['analysis_id'])


def run_expect_fail(query, ids, contains=None):
    job = main.create_analysis(AnalysisIn(query=query, dataset_ids=ids, provider='local'))
    aid = job['analysis_id']
    deadline = time.time() + 12
    while time.time() < deadline:
        row = main.get_analysis(aid)
        if row['status'] == 'failed':
            result = json.loads(row['result_json'] or '{}')
            message = result.get('error', '')
            if contains and contains.lower() not in message.lower():
                raise AssertionError(f"expected failure containing {contains!r}, got {message!r}")
            return result
        if row['status'] == 'completed':
            raise AssertionError('expected analysis to fail but it completed')
        time.sleep(0.05)
    raise TimeoutError(aid)


samples = main.load_demo()
indore = sorted([x for x in samples if x['filename'].startswith('Indore_')], key=lambda x: x['filename'])
assam = sorted([x for x in samples if x['filename'].startswith('Assam_') and x.get('modality') == 'sar'],
               key=lambda x: x['metadata'].get('acquired_at') or '')
assam_optical = next((x for x in samples if x['filename'].startswith('Assam_') and x.get('modality') == 'optical'), None)
assert len(indore) == 2 and len(assam) == 2 and assam_optical is not None

results = []

# 1) Temporal SAR flood
r = run('Show flooded areas around Assam between July and August 2025.', [x['id'] for x in assam])
assert r['intent'] == 'flood_detection'
assert len(r['source_datasets']) == 2
assert 'probable_flood_area_km2' in r['statistics']
assert r['geojson']['features']
assert r['provenance']['sources'] and 'confidence_breakdown' in r
assert r['confidence_breakdown']['temporal_support'] >= 0.9
results.append(('temporal_flood', r['method']))

# 2) Change detection fallback
r = run('Show urban expansion between these two images.', [x['id'] for x in indore])
assert r['intent'] == 'change_detection'
assert 'change_percent' in r['statistics']
results.append(('change_fallback', r['method']))

# 3) Vision assistant fallback is transparent when no VLM service is connected.
r = run('What is visible in this satellite image?', [indore[0]['id']])
assert r['intent'] == 'vision_question'
assert r['method'] == 'image_statistics'
assert any('VLM' in w or 'visual baseline' in w for w in r['warnings'])
results.append(('vision_offline_fallback', r['method']))

# 4) Mock a connected TEOChat service to test the actual VLM route contract.
orig_vlm = main.specialists.vlm.ask
main.specialists.vlm.ask = lambda query, paths: {
    'answer': 'The scene contains dense built-up areas, roads, and patches of vegetation.',
    'model': 'TEOChat test double',
}
r = run('Describe this satellite image in simple language.', [indore[0]['id']])
assert r['intent'] == 'vision_question'
assert r['method'] == 'TEOChat test double'
assert 'dense built-up areas' in r['answer']
assert r['statistics']['vision_assistant'] is True
results.append(('vision_assistant_route', r['method']))
main.specialists.vlm.ask = orig_vlm

# 5) Mock segment-geospatial contract to verify natural-language grounding route.
orig_seg = main.specialists.segmenter.segment_text
main.specialists.segmenter.segment_text = lambda image_path, prompt: {
    'model': 'segment-geospatial test double',
    'geojson': {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {'class': prompt},
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[75.72,22.64],[75.73,22.64],[75.73,22.65],[75.72,22.65],[75.72,22.64]]]
            }
        }]
    }
}
r = run('Highlight all buildings in this image.', [indore[0]['id']])
assert r['intent'] == 'grounded_segmentation'
assert r['statistics']['detected_object_count'] == 1
assert r['geojson']['features']
assert r['method'] == 'segment-geospatial test double'
results.append(('text_grounding_route', r['method']))
main.specialists.segmenter.segment_text = orig_seg

# 6) Mock Open-CD bridge output and verify trained model path wins over baseline.
orig_change = main.specialists.change.change_mask
mask = np.zeros((256, 256), dtype=np.uint8)
mask[80:170, 100:190] = 255
buf = io.BytesIO(); Image.fromarray(mask).save(buf, format='PNG')
main.specialists.change.change_mask = lambda a, b: {
    'mask_png': buf.getvalue(),
    'model': 'Open-CD test double',
    'confidence': 0.9,
}
r = run('Detect changes between these two images.', [x['id'] for x in indore])
assert r['intent'] == 'change_detection'
assert r['method'] == 'Open-CD test double'
assert r['confidence_type'] == 'specialist_model_output'
assert r['statistics']['change_percent'] > 0
results.append(('trained_change_route', r['method']))
main.specialists.change.change_mask = orig_change

# 7) Natural-language temporal vision route with mocked TEOChat uses two previews.
seen = {}
def temporal_vqa(query, paths):
    seen['count'] = len(paths)
    return {'answer': 'The later image shows additional built-up regions.', 'model': 'TEOChat temporal test double'}
main.specialists.vlm.ask = temporal_vqa
r = run('What are the most important visible differences between these two satellite images?', [x['id'] for x in indore])
assert r['intent'] == 'vision_question'
assert seen['count'] == 2
assert r['statistics']['temporal_images_used'] == 2
results.append(('temporal_vision_route', r['method']))
main.specialists.vlm.ask = orig_vlm

# 8) Vegetation temporal workflow uses two optical rasters and produces mapped statistics.
r = run('Where was vegetation lost between these two images?', [x['id'] for x in indore])
assert r['intent'] == 'vegetation_change'
assert len(r['source_datasets']) == 2
assert any(k in r['statistics'] for k in ('vegetation_loss_percent', 'changed_area_km2', 'loss_area_km2'))
results.append(('vegetation_temporal', r['method']))

# 9) Single-scene SAR flood query remains a valid non-temporal route.
r = run('Find flooded areas in this SAR scene.', [assam[-1]['id']])
assert r['intent'] == 'flood_detection'
assert len(r['source_datasets']) == 1
assert r['method']
assert r['geojson']['type'] == 'FeatureCollection'
results.append(('single_scene_flood', r['method']))

# 10) Location safety guard: never silently analyze Indore imagery for Guwahati.
failed = run_expect_fail('Show flooded areas around Guwahati in August 2025.', [indore[0]['id']], 'does not overlap')
assert 'Guwahati' in failed.get('error', '')
results.append(('wrong_location_guard', 'rejected mismatched imagery'))

# 11) SAR-specific semantic VQA routing prefers SARChat when available.
orig_sar_vlm = main.specialists.sar_vlm.ask
main.specialists.sar_vlm.ask = lambda query, paths: {
    'answer': 'The SAR scene shows a dark, low-backscatter water body and surrounding textured land.',
    'model': 'SARChat test double',
}
r = run('What is visible in this SAR image?', [assam[-1]['id']])
assert r['intent'] == 'vision_question'
assert r['method'] == 'SARChat test double'
assert 'low-backscatter' in r['answer']
results.append(('sar_vision_route', r['method']))
main.specialists.sar_vlm.ask = orig_sar_vlm

# 12) Optical + SAR joint route prefers a TerraMind-compatible fusion service.
# Re-label the earlier Assam demo scene as optical only for this routing contract test;
# geometry stays identical so overlap/compatibility checks remain meaningful.
with main.db() as con:
    con.execute('UPDATE datasets SET modality=? WHERE id=?', ('optical', assam[0]['id']))
orig_fuse = main.specialists.multimodal.fuse
fusion_calls = {'n': 0}
def fusion_once(query, optical_path, sar_path):
    fusion_calls['n'] += 1
    return {
    'answer': 'Optical texture and SAR backscatter jointly support a water-dominated interpretation in the highlighted zone.',
    'model': 'TerraMind test double',
    'confidence': 0.86,
    'confidence_type': 'multimodal_foundation_model',
    }
main.specialists.multimodal.fuse = fusion_once
r = run('Use both optical and SAR images for joint analysis', [assam[0]['id'], assam[1]['id']])
assert r['intent'] == 'multimodal_fusion'
assert r['method'] == 'TerraMind test double'
assert r['statistics']['multimodal_fusion'] is True
assert r['statistics']['modalities_used'] == ['optical', 'sar']
assert fusion_calls['n'] == 1, f"fusion service called {fusion_calls['n']} times; expected once"
results.append(('multimodal_fusion_route', r['method']))
main.specialists.multimodal.fuse = orig_fuse
with main.db() as con:
    con.execute('UPDATE datasets SET modality=? WHERE id=?', ('sar', assam[0]['id']))

# 13) Very-large-raster semantic questions prefer the LRS-VQA service contract.
orig_large = main.specialists.large_vlm.ask
orig_vlm2 = main.specialists.vlm.ask
row = main.get_dataset(indore[0]['id'])
md = json.loads(row['metadata_json'])
old_md = dict(md)
md['width'] = 8192; md['height'] = 6144
with main.db() as con:
    con.execute('UPDATE datasets SET metadata_json=? WHERE id=?', (json.dumps(md), indore[0]['id']))
main.specialists.large_vlm.ask = lambda query, paths: {
    'answer': 'The high-resolution scene contains dense urban blocks with road corridors and sparse vegetation.',
    'model': 'LRS-VQA test double',
}
main.specialists.vlm.ask = lambda query, paths: (_ for _ in ()).throw(AssertionError('generic VLM should not win large-RSI routing'))
r = run('Describe this large satellite image', [indore[0]['id']])
assert r['intent'] == 'vision_question'
assert r['method'] == 'LRS-VQA test double'
results.append(('large_rsi_vision_route', r['method']))
main.specialists.large_vlm.ask = orig_large
main.specialists.vlm.ask = orig_vlm2
with main.db() as con:
    con.execute('UPDATE datasets SET metadata_json=? WHERE id=?', (json.dumps(old_md), indore[0]['id']))

# 14) Unsupported forecasting is rejected instead of producing a fake image summary.
failed = run_expect_fail('Predict which parts of Assam will flood next month', [assam[-1]['id']], 'Forecasting is not enabled')
results.append(('unsupported_forecast_guard', 'rejected unsupported forecast'))

print('E2E MATRIX PASS')
for name, method in results:
    print(f'- {name}: {method}')
