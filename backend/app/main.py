from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio
from rasterio.transform import from_origin
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .geo_tools import (
    make_preview, read_raster, compatibility,
    change_detection, flood_detection, temporal_flood_detection,
    vegetation_change, summarize_image, external_change_detection,
    grounded_segmentation_result, visual_answer_result,
)
from .query_parser import parse_query
from .satellite_catalog import retrieve_sentinel1_pair, resolve_location_online
from .flood_model import model_status
from .openearth_adapter import OpenEarthAdapter
from .specialist_adapters import SpecialistRegistry
from .demo_data import (
    DEMO_SPECS,
    _write_assam_optical_demo,
    _write_assam_sar_demo,
    _write_optical_demo,
    period_label_for,
)

BASE = Path(__file__).resolve().parents[1]
if os.getenv('SATQUERY_DATA_DIR'):
    DATA = Path(os.getenv('SATQUERY_DATA_DIR'))
elif os.getenv('VERCEL'):
    DATA = Path('/tmp/satquery')
else:
    DATA = BASE / 'data'
UPLOADS = DATA / 'uploads'
PREVIEWS = DATA / 'previews'
RESULTS = DATA / 'results'
DB = DATA / 'satquery.db'
BAKED = Path(os.getenv('SATQUERY_BAKED_DIR', str(BASE / 'data' / 'baked')))
for d in [UPLOADS, PREVIEWS, RESULTS]:
    d.mkdir(parents=True, exist_ok=True)

MAX_BYTES = int(os.getenv('SATQUERY_MAX_UPLOAD_MB', '250')) * 1024 * 1024
ALLOWED = {'.tif', '.tiff', '.png', '.jpg', '.jpeg'}

app = FastAPI(title='SatQuery AI E2E API', version='4.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv('SATQUERY_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()],
    allow_methods=['*'],
    allow_headers=['*'],
)
oea = OpenEarthAdapter()
specialists = SpecialistRegistry()


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS datasets(
          id TEXT PRIMARY KEY, filename TEXT, path TEXT, preview_path TEXT, modality TEXT,
          metadata_json TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS analyses(
          id TEXT PRIMARY KEY, query TEXT, dataset_ids_json TEXT, status TEXT, intent TEXT,
          provider TEXT, events_json TEXT, result_json TEXT, created_at TEXT, completed_at TEXT
        );
        ''')


init_db()


def dataset_row(row):
    if not row:
        return None
    md = json.loads(row['metadata_json'])
    return {
        'id': row['id'],
        'filename': row['filename'],
        'modality': row['modality'],
        'metadata': md,
        'created_at': row['created_at'],
        'preview_url': f"/api/v1/datasets/{row['id']}/preview",
    }


def get_dataset(did: str):
    with db() as con:
        return con.execute('SELECT * FROM datasets WHERE id=?', (did,)).fetchone()


def _register_demo_file(fname: str, mod: str, kind: str) -> Dict[str, Any]:
    """Ensure a demo dataset exists on disk (baked copy when present, else
    synthesize) and register it in the database. IDs are deterministic so every
    container instance exposes exactly the same dataset IDs."""
    did = 'ds_' + hashlib.sha1(fname.encode('utf-8')).hexdigest()[:12]
    dest = UPLOADS / f'{did}.tif'
    png = PREVIEWS / f'{did}.png'
    baked_src = BAKED / fname
    if baked_src.exists():
        shutil.copy2(baked_src, dest)
        baked_png = BAKED / (Path(fname).stem + '.png')
        if baked_png.exists():
            shutil.copy2(baked_png, png)
        else:
            make_preview(dest, png)
    else:
        if kind == 'optical_before':
            _write_optical_demo(dest, seed=3, changed=False)
        elif kind == 'optical_after':
            _write_optical_demo(dest, seed=3, changed=True)
        elif kind == 'optical_assam':
            _write_assam_optical_demo(dest, seed=23, acquired_at='2025-08-19')
        elif kind == 'sar_before':
            _write_assam_sar_demo(dest, seed=17, flood_stage='before', acquired_at='2025-07-18')
        else:
            _write_assam_sar_demo(dest, seed=17, flood_stage='after', acquired_at='2025-08-19')
        make_preview(dest, png)
    md = read_raster(dest)['meta']
    md['period_label'] = period_label_for(kind)
    md['demo_data'] = True
    with db() as con:
        con.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?)', (did, fname, str(dest), str(png), mod, json.dumps(md), now()))
    return dataset_row(get_dataset(did))


def _demo_registered(fname: str):
    with db() as con:
        return con.execute('SELECT * FROM datasets WHERE filename=?', (fname,)).fetchone()


def seed_demo_if_empty():
    """Restore baked demo datasets into this container instance on startup.

    Vercel container storage (/tmp) is ephemeral and per-instance, so every
    cold start restores the demo datasets from the baked image assets."""
    if not BAKED.exists():
        return
    with db() as con:
        n = con.execute('SELECT COUNT(*) AS c FROM datasets').fetchone()['c']
    if n > 0:
        return
    for fname, mod, kind in DEMO_SPECS:
        if not _demo_registered(fname):
            _register_demo_file(fname, mod, kind)


seed_demo_if_empty()


def get_analysis(aid: str):
    with db() as con:
        return con.execute('SELECT * FROM analyses WHERE id=?', (aid,)).fetchone()


def update_analysis(aid: str, **fields):
    if not fields:
        return
    cols = ', '.join([f'{k}=?' for k in fields])
    vals = list(fields.values()) + [aid]
    with db() as con:
        con.execute(f'UPDATE analyses SET {cols} WHERE id=?', vals)


def event(aid: str, stage: str, title: str, detail: str, state='done'):
    row = get_analysis(aid)
    events = json.loads(row['events_json'] or '[]')
    events.append({'ts': now(), 'stage': stage, 'title': title, 'detail': detail, 'state': state})
    update_analysis(aid, events_json=json.dumps(events))


def _bbox_intersects(a, b) -> bool:
    if not a or not b:
        return True
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def _row_modality(row: Any) -> str:
    try:
        return (row['modality'] or '').lower()
    except Exception:
        return str((row or {}).get('modality') or '').lower()


def _row_meta(row: Any) -> Dict[str, Any]:
    try:
        raw = row['metadata_json']
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return dict((row or {}).get('metadata') or {})


def _vision_specialist_ask(query: str, rows: List[Dict[str, Any]], image_paths: List[str],
                           source_paths: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Sensor- and scale-aware semantic VLM routing.

    Routing priority:
      1. Large-RSI specialist when the original raster is very large.
      2. SAR-domain VLM for SAR semantic questions.
      3. The EO-VLM service for single/temporal general EO VQA.

    The VLM service performs its own GeoTIFF preprocessing, so the ORIGINAL
    raster files are sent (``source_paths``) wherever available; previews remain
    a fallback. SAR semantic interpretation is refused when no SAR-specialized
    model is connected instead of inventing radar-based meaning.
    """
    effective = source_paths if source_paths else image_paths
    if rows:
        meta = _row_meta(rows[0])
        longest_side = max(int(meta.get('width') or 0), int(meta.get('height') or 0))
        if longest_side >= int(os.getenv('SATQUERY_LARGE_RSI_THRESHOLD', '4096')):
            large_answer = specialists.large_vlm.ask(query, effective)
            if large_answer:
                return large_answer

        if _row_modality(rows[0]) == 'sar':
            sar_answer = specialists.sar_vlm.ask(query, effective)
            if sar_answer:
                return sar_answer
            return {'answer': None, 'sar_unavailable': True}

    return specialists.vlm.ask(query, effective)


def _is_model_backed(result: Dict[str, Any]) -> bool:
    info = result.get('model_info') or {}
    if isinstance(info, dict):
        if info.get('model_backed') is True:
            return True
        before = info.get('before') or {}
        after = info.get('after') or {}
        if isinstance(before, dict) and isinstance(after, dict) and before.get('model_backed') and after.get('model_backed'):
            return True
    conf_type = str(result.get('confidence_type') or '')
    return conf_type in {'specialist_model_output', 'multimodal_foundation_model', 'model_assisted', 'model_assisted_temporal'}


def _confidence_breakdown(result: Dict[str, Any], datasets: List[Any], query_context: Dict[str, Any]) -> Dict[str, Any]:
    """Explain why the operational score is high/medium/low without pretending calibration."""
    rows = datasets or []
    metas = [_row_meta(x) for x in rows]
    has_crs = bool(metas) and all(bool(m.get('crs')) for m in metas)
    has_dates = bool(metas) and all(bool(m.get('acquired_at') or m.get('period_label')) for m in metas[:2])
    temporal = bool(query_context.get('temporal'))
    geo_features = len((result.get('geojson') or {}).get('features') or [])
    model_backed = _is_model_backed(result)
    method = str(result.get('method') or '')

    input_quality = 0.95 if has_crs else 0.72
    if any(m.get('nodata') is not None for m in metas):
        input_quality = min(input_quality, 0.90)
    model_support = 0.92 if model_backed else (0.72 if 'adaptive' in method or 'heuristic' in str(result.get('confidence_type')) else 0.78)
    spatial_support = 0.94 if geo_features and has_crs else (0.78 if has_crs else 0.62)
    temporal_support = 0.94 if temporal and len(rows) >= 2 and has_dates else (0.65 if temporal else 0.90)
    evidence_coverage = 0.93 if (geo_features or result.get('answer')) else 0.65

    return {
        'input_quality': round(input_quality, 2),
        'model_support': round(model_support, 2),
        'spatial_support': round(spatial_support, 2),
        'temporal_support': round(temporal_support, 2),
        'evidence_coverage': round(evidence_coverage, 2),
        'model_backed': model_backed,
        'note': 'Components explain operational evidence strength; they are not calibrated scientific probabilities.',
    }


def _provenance(result: Dict[str, Any], datasets: List[Any], provider: str) -> Dict[str, Any]:
    model_info = result.get('model_info') or {}
    method = result.get('method') or 'unknown'
    model_backed = _is_model_backed(result)
    sources = []
    for row in datasets:
        md = _row_meta(row)
        sources.append({
            'filename': row['filename'],
            'modality': _row_modality(row) or 'unknown',
            'sensor_or_source': md.get('platform') or md.get('source') or ('Sentinel-1' if _row_modality(row) == 'sar' else 'uploaded imagery'),
            'acquired_at': md.get('acquired_at') or md.get('period_label'),
            'stac_id': md.get('stac_id'),
            'crs': md.get('crs'),
            'resolution': md.get('resolution'),
        })

    model_name = method
    if isinstance(model_info, dict):
        if model_info.get('model'):
            model_name = model_info.get('model')
        elif isinstance(model_info.get('after'), dict) and model_info['after'].get('model'):
            model_name = model_info['after'].get('model')

    benchmark = None
    if model_backed and 'Sentinel Flood Mapper' in str(model_name):
        benchmark = {
            'dataset_scope': 'Published held-out flood-event test set from the upstream Sentinel-Flood-Mapper project',
            'iou': 0.6128,
            'f1': 0.7599,
            'precision': 0.8719,
            'recall': 0.6735,
            'accuracy': 0.9162,
            'important': 'These are upstream benchmark metrics, not accuracy measured on the current user scene.',
        }

    return {
        'execution_provider': provider,
        'method': method,
        'model_display': str(model_name),
        'model_backed': model_backed,
        'fallback_used': not model_backed,
        'fallback_reason': (model_info or {}).get('fallback_reason'),
        'model_version': (model_info or {}).get('model_version'),
        'model_backend': (model_info or {}).get('backend'),
        'latency_ms': (model_info or {}).get('latency_ms'),
        'model_confidence': (model_info or {}).get('model_confidence'),
        'sources': sources,
        'benchmark': benchmark,
    }


def _dataset_location_warning(dataset, query_context: Dict[str, Any]) -> Optional[str]:
    loc = query_context.get('location') or {}
    loc_bbox = loc.get('bbox')
    md = json.loads(dataset['metadata_json'])
    ds_bbox = md.get('bounds_wgs84')
    if loc_bbox and ds_bbox and not _bbox_intersects(loc_bbox, ds_bbox):
        return f"Selected dataset '{dataset['filename']}' does not overlap the query location {loc.get('name')}."
    return None


def _save_dataset(path: Path, filename: str, modality: str, extra_meta: Optional[Dict[str, Any]] = None):
    did = 'ds_' + uuid.uuid4().hex[:12]
    dest = UPLOADS / f'{did}{path.suffix.lower() or ".tif"}'
    if path.resolve() != dest.resolve():
        path.replace(dest)
    preview = PREVIEWS / f'{did}.png'
    make_preview(dest, preview)
    md = read_raster(dest)['meta']
    if extra_meta:
        md.update(extra_meta)
    with db() as con:
        con.execute(
            'INSERT INTO datasets VALUES(?,?,?,?,?,?,?)',
            (did, filename, str(dest), str(preview), modality, json.dumps(md), now()),
        )
    return get_dataset(did)


def _auto_retrieve(aid: str, query_context: Dict[str, Any]) -> List[Any]:
    if not query_context.get('can_auto_retrieve'):
        raise ValueError('No input imagery was selected and the query does not contain enough location/date information for automatic retrieval.')
    loc = query_context.get('location') or {}
    dr = query_context.get('date_range') or {}
    event(aid, 'retrieval', 'Satellite retrieval started', f"Searching Sentinel-1 RTC for {loc.get('name')} across {dr.get('start_date')} → {dr.get('end_date')}.")
    prefix = 'retr_' + uuid.uuid4().hex[:8]
    retrieved = retrieve_sentinel1_pair(query_context, UPLOADS, prefix)
    rows = []
    for item in retrieved:
        p = Path(item['path'])
        # retrieve_sentinel1_pair already writes inside UPLOADS. Move through a temp
        # path so _save_dataset can apply the normal dataset naming convention.
        tmp = UPLOADS / f"tmp_{uuid.uuid4().hex[:8]}.tif"
        p.replace(tmp)
        row = _save_dataset(tmp, item['filename'], item['modality'], item.get('extra_meta'))
        rows.append(row)
        md = json.loads(row['metadata_json'])
        event(aid, 'retrieval', 'Sentinel-1 scene ready', f"{row['filename']} · acquired {md.get('acquired_at') or 'unknown date'} · {md.get('stac_id') or 'STAC item'}")
    update_analysis(aid, dataset_ids_json=json.dumps([r['id'] for r in rows]))
    return rows


def _ordered_temporal(datasets: List[Any]) -> List[Any]:
    def key(row):
        md = json.loads(row['metadata_json'])
        return md.get('acquired_at') or md.get('period_label') or row['created_at']
    return sorted(datasets, key=key)


def run_analysis(aid: str):
    row = get_analysis(aid)
    query = row['query']
    ids = json.loads(row['dataset_ids_json'] or '[]')
    datasets = [get_dataset(x) for x in ids if get_dataset(x)]
    try:
        update_analysis(aid, status='validating_input')
        query_context = parse_query(query, len(datasets))
        intent = query_context['intent']
        update_analysis(aid, intent=intent)
        if intent == 'unsupported':
            reason = query_context.get('unsupported_reason') or 'This request is outside the supported Earth-observation capabilities.'
            event(aid, 'intent', 'Unsupported capability', reason, 'warning')
            raise ValueError(reason)

        # Unknown location phrases can be geocoded at runtime. The parser never
        # pretends that an unresolved phrase has real coordinates.
        if not query_context.get('location') and query_context.get('unresolved_location_text'):
            candidate = query_context['unresolved_location_text']
            event(aid, 'intent', 'Resolving place name', f"Trying to resolve '{candidate}' for geospatial analysis.")
            resolved = resolve_location_online(candidate)
            if resolved:
                query_context['location'] = resolved
                event(aid, 'intent', 'Place resolved', f"{candidate} → {resolved.get('name')}")
            elif query_context.get('can_auto_retrieve'):
                raise ValueError(f"Could not resolve the requested place '{candidate}'. Upload imagery for the area or use a more specific place name.")

        loc = query_context.get('location')
        dr = query_context.get('date_range')
        parsed_bits = [f"Intent: {intent.replace('_', ' ')}"]
        if loc:
            parsed_bits.append(f"Location: {loc.get('name')}")
        if dr:
            parsed_bits.append(f"Time: {dr.get('start_date')} → {dr.get('end_date')}")
        event(aid, 'intent', 'Query understood', ' · '.join(parsed_bits))

        if not datasets:
            datasets = _auto_retrieve(aid, query_context)

        # Protect against mislabeled/fake-location files. If the query contains
        # enough information for retrieval, replace mismatched inputs instead of
        # silently analyzing the wrong place.
        location_warnings = [w for ds in datasets if (w := _dataset_location_warning(ds, query_context))]
        if location_warnings:
            if query_context.get('can_auto_retrieve'):
                event(aid, 'validation', 'Selected imagery does not match the requested place', ' '.join(location_warnings) + ' SatQuery will retrieve matching Sentinel-1 scenes instead.', 'warning')
                datasets = _auto_retrieve(aid, query_context)
            else:
                raise ValueError(location_warnings[0] + ' Choose imagery that overlaps the requested location.')

        # Temporal flood analysis requires a before/after SAR pair. The user may
        # provide it manually, or SatQuery can retrieve it from the parsed query.
        if intent == 'flood_detection' and query_context.get('temporal'):
            sar_pair_ok = len(datasets) >= 2 and all((d['modality'] or '').lower() == 'sar' for d in datasets[:2])
            if not sar_pair_ok and query_context.get('can_auto_retrieve'):
                event(aid, 'sensor', 'SAR temporal pair required', 'The selected inputs are incomplete or not SAR. Retrieving a matching Sentinel-1 before/after pair.', 'warning')
                datasets = _auto_retrieve(aid, query_context)
            elif not sar_pair_ok:
                raise ValueError('Temporal flood mapping requires two overlapping SAR datasets (earlier and later).')

        update_analysis(aid, status='planning')
        provider = 'local'
        external_plan = None
        if row['provider'] in ('auto', 'external'):
            external_plan = oea.plan(query, datasets[0]['path'] if datasets else None)
            if external_plan:
                provider = 'external_agent'
                event(aid, 'planner', 'External agent plan received', 'A structured tool plan was received and will be constrained by the SatQuery tool router.')
            elif row['provider'] == 'external':
                event(aid, 'planner', 'External planner unavailable', 'Using the built-in SatQuery planner and deterministic tool router.', 'warning')
        update_analysis(aid, provider=provider)

        if intent in ('change_detection', 'vegetation_change') or (intent == 'flood_detection' and query_context.get('temporal')):
            if len(datasets) < 2:
                raise ValueError('This temporal analysis requires two datasets.')
            datasets = _ordered_temporal(datasets)[:2]
            comp = compatibility(datasets[0]['path'], datasets[1]['path'])
            event(aid, 'validation', 'Temporal inputs checked', json.dumps(comp))
            if not comp['compatible']:
                raise ValueError('Selected datasets do not overlap.')
        elif intent == 'multimodal_fusion':
            if len(datasets) < 2:
                raise ValueError('Optical + SAR joint analysis requires two overlapping datasets: one optical and one SAR.')
            mods = {_row_modality(x) for x in datasets}
            if not {'optical', 'sar'}.issubset(mods):
                found = ', '.join(sorted(mods)) or 'none'
                raise ValueError(
                    f'Optical + SAR joint analysis requires one dataset marked optical and one marked SAR, '
                    f'but the selected inputs are marked: {found}. Upload an optical scene (Sentinel-2/true-colour) '
                    'and a SAR scene (Sentinel-1), or pick one of each from the library.'
                )
            optical = next(x for x in datasets if _row_modality(x) == 'optical')
            sar = next(x for x in datasets if _row_modality(x) == 'sar')
            datasets = [optical, sar]
            comp = compatibility(datasets[0]['path'], datasets[1]['path'])
            event(aid, 'validation', 'Cross-modal inputs checked', json.dumps(comp))
            if not comp['compatible']:
                raise ValueError('Selected optical and SAR datasets do not overlap.')
        else:
            event(aid, 'validation', 'Input checked', f"{datasets[0]['filename']} is ready for analysis.")

        update_analysis(aid, status='preprocessing')
        if intent == 'flood_detection':
            if query_context.get('preferred_sensor') == 'sar':
                event(aid, 'sensor', 'Sensor-aware routing', 'SAR selected for flood analysis because radar can observe the surface through cloud cover and is appropriate for monsoon-period mapping.')
            if loc and loc.get('coverage_note'):
                event(aid, 'sensor', 'AOI scope', loc['coverage_note'], 'warning')

        plan_text = (
            external_plan.get('raw_output', 'External structured plan')[:800]
            if external_plan else
            ("Flood query → Sentinel-1/SAR → temporal water masks → persistent-water suppression → polygonize → area → evidence gate" if intent == 'flood_detection' and len(datasets) >= 2
             else f"{intent} → geospatial processing → evidence validation")
        )
        event(aid, 'planner', 'Task plan created', plan_text)

        update_analysis(aid, status='running_models')
        out = RESULTS / f'{aid}_overlay.png'
        if intent == 'change_detection':
            # Prefer a trained Open-CD specialist when its isolated service is
            # available; fall back to the deterministic aligned-difference tool.
            trained = specialists.change.change_mask(datasets[0]['preview_path'], datasets[1]['preview_path'])
            if trained:
                event(aid, 'tool', 'Trained change specialist selected', f"{trained.get('model')} → Polygonize → Area statistics")
                result = external_change_detection(
                    datasets[0]['path'], datasets[1]['path'], trained['mask_png'], out,
                    trained.get('model', 'Open-CD'), trained.get('confidence', 0.88),
                )
            else:
                event(aid, 'tool', 'Change baseline selected', 'Aligned image difference → Polygonize → Area statistics. Connect OPENCD_URL for trained inference.', 'warning')
                result = change_detection(datasets[0]['path'], datasets[1]['path'], out)
        elif intent == 'vegetation_change':
            event(aid, 'tool', 'Tools selected', 'Vegetation index → Temporal difference → Polygonize')
            result = vegetation_change(datasets[0]['path'], datasets[1]['path'], out)
        elif intent == 'flood_detection' and len(datasets) >= 2:
            event(aid, 'tool', 'Temporal SAR flood workflow', 'Before-water mask + after-water mask → persistent water removal → probable new inundation.')
            result = temporal_flood_detection(datasets[0]['path'], datasets[1]['path'], out)
            event(aid, 'tool', 'Flood routing rationale', result.get('routing_reason', 'Temporal SAR workflow selected.'))
        elif intent == 'flood_detection':
            mod = datasets[0]['modality'] or 'auto'
            event(aid, 'tool', 'Single-scene flood workflow', f"Input modality: {mod}. Water specialist selected.")
            result = flood_detection(datasets[0]['path'], out, mod)
            event(aid, 'tool', 'Routing rationale', result.get('routing_reason', 'Flood specialist selected.'))
        elif intent == 'multimodal_fusion':
            optical = next((x for x in datasets if _row_modality(x) == 'optical'), None)
            sar = next((x for x in datasets if _row_modality(x) == 'sar'), None)
            fused = specialists.multimodal.fuse(query, optical['path'], sar['path']) if optical and sar else None
            if fused and fused.get('answer'):
                model_name = fused.get('model', 'TerraMind')
                event(aid, 'tool', 'Multimodal EO fusion specialist selected', f"{model_name} received aligned optical + SAR inputs.")
                result = visual_answer_result(optical['path'], out, fused['answer'], model_name)
                result['statistics'].update({'multimodal_fusion': True, 'modalities_used': ['optical', 'sar']})
                result['confidence'] = float(fused.get('confidence', result.get('confidence', 0.78)))
                result['confidence_type'] = fused.get('confidence_type', 'multimodal_foundation_model')
                result['warnings'] = list(fused.get('warnings') or []) + result.get('warnings', [])
            else:
                image_paths = [optical['preview_path'], sar['preview_path']] if optical and sar else [x['preview_path'] for x in datasets[:2]]
                vqa = specialists.vlm.ask(query, image_paths)
                if vqa and vqa.get('answer'):
                    event(aid, 'tool', 'Cross-modal semantic fallback selected', 'TerraMind task service is offline; TEOChat is reasoning over optical + SAR previews without claiming feature-level fusion.', 'warning')
                    result = visual_answer_result(optical['path'] if optical else datasets[0]['path'], out, vqa['answer'], vqa.get('model', 'TEOChat'), temporal=True, second_path=(sar['path'] if sar else datasets[1]['path']))
                    result['statistics'].update({'multimodal_fusion': False, 'modalities_used': ['optical', 'sar']})
                    result['warnings'].append('This answer is cross-modal semantic reasoning, not TerraMind feature-level fusion. Connect TERRAMIND_URL for a task-specific multimodal model.')
                else:
                    event(aid, 'tool', 'Multimodal specialist unavailable', 'Connect TERRAMIND_URL for optical+SAR feature-level analysis or TEOCHAT_URL for semantic two-image reasoning.', 'warning')
                    result = summarize_image(optical['path'] if optical else datasets[0]['path'], out)
                    result['statistics'].update({'multimodal_fusion': False, 'modalities_used': ['optical', 'sar']})
                    result['warnings'].append('No semantic multimodal model is connected; only the optical/local visual baseline was produced.')

        elif intent == 'grounded_segmentation':
            target = query_context.get('target_object') or 'target object'
            segmented = specialists.segmenter.segment_text(datasets[0]['path'], target)
            if segmented:
                event(aid, 'tool', 'Language-guided segmentation selected', f"Text prompt: {target}. Geospatial polygons requested from the segmentation specialist.")
                result = grounded_segmentation_result(
                    datasets[0]['path'], out, segmented['geojson'], target, segmented.get('model', 'segment-geospatial'),
                )
            else:
                # A VLM can still answer the question semantically when pixel
                # grounding is unavailable, but SatQuery does not fake polygons.
                image_paths = [datasets[0]['preview_path']]
                vqa = _vision_specialist_ask(query, datasets, image_paths)
                if vqa and vqa.get('answer'):
                    event(aid, 'tool', 'Vision assistant fallback', 'Text segmentation service unavailable; semantic remote-sensing VQA used without fabricated masks.', 'warning')
                    result = visual_answer_result(datasets[0]['path'], out, vqa['answer'], vqa.get('model', 'TEOChat'))
                    result['warnings'].append('No pixel-grounded mask was produced because the text-segmentation specialist is offline.')
                else:
                    event(aid, 'tool', 'Grounding specialist unavailable', 'Connect SAMGEO_URL for text-prompt polygons, SARCHAT_URL for SAR VQA, or TEOCHAT_URL for general/temporal EO VQA.', 'warning')
                    result = summarize_image(datasets[0]['path'], out)
                    result['warnings'].append(f"Could not ground '{target}' because no language-guided segmentation/VLM specialist is connected.")
        elif intent in ('vision_question', 'image_summary'):
            use_rows = datasets[:2] if query_context.get('temporal') and len(datasets) >= 2 else datasets[:1]
            image_paths = [x['preview_path'] for x in use_rows]
            source_paths = [x['path'] for x in use_rows]
            vqa = _vision_specialist_ask(query, datasets, image_paths, source_paths=source_paths)
            if vqa and vqa.get('answer'):
                model_name = vqa.get('model_name') or vqa.get('model', 'Remote-sensing VLM')
                event(aid, 'tool', 'Remote-sensing vision assistant selected', f"{model_name} answered using {len(source_paths)} source image(s).")
                result = visual_answer_result(
                    datasets[0]['path'], out, vqa['answer'], model_name,
                    temporal=len(image_paths) > 1, second_path=(datasets[1]['path'] if len(image_paths) > 1 else None),
                    model_info=vqa, latency_ms=vqa.get('latency_ms'), model_confidence=vqa.get('model_confidence'),
                )
                result['warnings'].extend(list(vqa.get('warnings') or []))
            elif isinstance(vqa, dict) and vqa.get('sar_unavailable'):
                event(aid, 'tool', 'SAR semantic interpretation unavailable', 'No SAR-specialized VLM is connected; refusing to send radar imagery to an optical-semantics vision model.', 'warning')
                result = summarize_image(datasets[0]['path'], out)
                result['warnings'] = ['Vision specialist unavailable for SAR semantic interpretation.'] + list(result.get('warnings', []))
            elif isinstance(vqa, dict) and vqa.get('reason'):
                event(aid, 'tool', 'Vision assistant declined input', vqa['reason'], 'warning')
                result = summarize_image(datasets[0]['path'], out)
                result['warnings'] = [vqa['reason']] + list(result.get('warnings', []))
            else:
                event(aid, 'tool', 'Vision baseline selected', 'Remote-sensing VLM service is offline; using local image statistics without pretending to be a semantic VLM.', 'warning')
                result = summarize_image(datasets[0]['path'], out)
        else:
            event(aid, 'tool', 'Tool selected', 'Image description / image-statistics baseline')
            result = summarize_image(datasets[0]['path'], out)

        update_analysis(aid, status='geo_processing')
        event(aid, 'geo', 'Geospatial processing complete', f"Method: {result.get('method')}. GeoJSON features: {len(result.get('geojson', {}).get('features', []))}")

        update_analysis(aid, status='validating_evidence')
        conf = float(result.get('confidence', 0.5))
        label = 'High' if conf >= .85 else 'Medium' if conf >= .65 else 'Low' if conf >= .45 else 'Insufficient'
        conf_type = result.get('confidence_type', 'operational')
        event(aid, 'evidence', 'Evidence gate complete', f"{label} operational confidence ({conf*100:.1f}%). Type: {conf_type}. Model-backed: {_is_model_backed(result)}. This is not presented as a calibrated scientific probability.")

        stats = result.get('statistics', {})
        location_name = (loc or {}).get('name') or 'the analyzed AOI'
        periods = (dr or {}).get('periods') or []
        if result.get('answer'):
            answer = result['answer']
        elif intent == 'flood_detection' and len(datasets) >= 2:
            p1 = periods[0]['label'] if len(periods) >= 2 else json.loads(datasets[0]['metadata_json']).get('period_label', 'the first period')
            p2 = periods[-1]['label'] if len(periods) >= 2 else json.loads(datasets[1]['metadata_json']).get('period_label', 'the second period')
            area = stats.get('probable_flood_area_km2', 0)
            answer = (
                f"Between {p1} and {p2}, SatQuery detected approximately {area} km² of probable new inundation within {location_name}. "
                f"Water visible in both periods was treated as persistent water and excluded from the new-flood estimate."
            )
        elif intent == 'change_detection':
            answer = f"Detected approximately {stats.get('change_percent', 0)}% changed pixels between the selected inputs."
            if stats.get('changed_area_km2') is not None:
                answer += f" Geospatially estimated changed area: {stats['changed_area_km2']} km²."
        elif intent == 'vegetation_change':
            answer = f"Estimated vegetation-loss footprint is {stats.get('vegetation_loss_percent', 0)}% of the analyzed image."
            if stats.get('loss_area_km2') is not None:
                answer += f" Estimated loss area: {stats['loss_area_km2']} km²."
        elif intent == 'flood_detection':
            answer = f"Detected a water/flood-like footprint over approximately {stats.get('water_or_flood_percent', 0)}% of the selected scene."
            if stats.get('affected_area_km2') is not None:
                answer += f" Estimated affected area: {stats['affected_area_km2']} km²."
        elif intent == 'multimodal_fusion':
            answer = 'Optical + SAR analysis completed using the available specialist/fallback path. Review the provenance and warnings below to see whether feature-level fusion or semantic comparison was used.'

        elif intent == 'grounded_segmentation':
            target = stats.get('target') or query_context.get('target_object') or 'target object'
            answer = f"Detected {stats.get('detected_object_count', 0)} mapped {target} region(s)."
            if stats.get('detected_area_km2') is not None:
                answer += f" Combined mapped area: {stats['detected_area_km2']} km²."
        else:
            answer = f"Image analysis completed. Mean brightness is {stats.get('mean_brightness')}; green-dominant coverage is {stats.get('green_dominant_percent')}%."

        source_rows = [dataset_row(x) for x in datasets]
        map_bounds = result.get('map_bounds_wgs84') or (source_rows[-1].get('metadata', {}).get('bounds_wgs84') if source_rows else None)
        confidence_breakdown = _confidence_breakdown(result, datasets, query_context)
        provenance = _provenance(result, datasets, provider)
        final = {
            'analysis_id': aid,
            'intent': intent,
            'provider': provider,
            'answer': answer,
            'confidence': conf,
            'confidence_label': label,
            'confidence_type': conf_type,
            'confidence_breakdown': confidence_breakdown,
            'provenance': provenance,
            'statistics': stats,
            'warnings': result.get('warnings', []),
            'method': result.get('method'),
            'model_info': result.get('model_info'),
            'legend': result.get('legend', []),
            'query_context': query_context,
            'geojson': result.get('geojson', {'type': 'FeatureCollection', 'features': []}),
            'overlay_url': f'/api/v1/analyses/{aid}/overlay',
            'geojson_url': f'/api/v1/analyses/{aid}/geojson',
            'source_datasets': source_rows,
            'map_context': {'bounds_wgs84': map_bounds, 'location': location_name},
        }
        update_analysis(aid, status='completed', result_json=json.dumps(final), completed_at=now())
        event(aid, 'response', 'Grounded response generated', 'Interactive map, overlay, statistics, warnings, source scenes and evidence are ready.')
    except Exception as exc:
        event(aid, 'error', 'Analysis failed', str(exc), 'error')
        update_analysis(aid, status='failed', result_json=json.dumps({'error': str(exc)}), completed_at=now())


class AnalysisIn(BaseModel):
    query: str
    dataset_ids: List[str] = []
    provider: str = 'auto'


class QueryIn(BaseModel):
    query: str
    dataset_count: int = 0


@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'time': now(), 'agent_bridge': oea.health(), 'flood_model': model_status(), 'specialists': specialists.health()}


@app.post('/api/v1/query/parse')
def query_parse(inp: QueryIn):
    return parse_query(inp.query, max(0, int(inp.dataset_count or 0)))


@app.get('/api/v1/datasets')
def list_datasets():
    with db() as con:
        rows = con.execute('SELECT * FROM datasets ORDER BY created_at DESC').fetchall()
    return [dataset_row(x) for x in rows]


@app.post('/api/v1/datasets')
async def upload_dataset(file: UploadFile = File(...), modality: str = Form('auto')):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, 'Unsupported file type.')
    did = 'ds_' + uuid.uuid4().hex[:12]
    dest = UPLOADS / f'{did}{suffix}'
    size = 0
    with dest.open('wb') as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, 'File too large.')
            f.write(chunk)
    try:
        raster = read_raster(dest)
        if raster['meta']['width'] * raster['meta']['height'] > 120_000_000:
            dest.unlink(missing_ok=True)
            raise HTTPException(413, 'Raster pixel count exceeds safety limit.')
        preview = PREVIEWS / f'{did}.png'
        make_preview(dest, preview)
        md = raster['meta']
    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f'Could not read image/raster: {exc}')
    inferred = modality
    if modality == 'auto':
        n = (file.filename or '').lower()
        inferred = 'sar' if 'sar' in n or 'sentinel-1' in n or 's1_' in n or md.get('count') == 2 else 'optical'
    with db() as con:
        con.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?)', (did, file.filename, str(dest), str(preview), inferred, json.dumps(md), now()))
    row = dataset_row(get_dataset(did))
    if row:
        try:
            row['preview_b64'] = 'data:image/png;base64,' + base64.b64encode(preview.read_bytes()).decode('ascii')
        except Exception:
            pass
    return row


@app.get('/api/v1/datasets/{did}/preview')
def dataset_preview(did: str):
    row = get_dataset(did)
    if not row:
        raise HTTPException(404, 'Dataset not found')
    p = Path(row['preview_path'])
    if not p.exists() and Path(row['path']).exists():
        try:
            PREVIEWS.mkdir(parents=True, exist_ok=True)
            make_preview(Path(row['path']), p)
        except Exception:
            pass
    if not p.exists():
        raise HTTPException(404, 'Preview image is not ready')
    return FileResponse(p, media_type='image/png')


@app.delete('/api/v1/datasets/{did}')
def delete_dataset(did: str):
    row = get_dataset(did)
    if not row:
        raise HTTPException(404, 'Dataset not found')
    Path(row['path']).unlink(missing_ok=True)
    Path(row['preview_path']).unlink(missing_ok=True)
    with db() as con:
        con.execute('DELETE FROM datasets WHERE id=?', (did,))
    return {'ok': True}


@app.post('/api/v1/analyses')
def create_analysis(inp: AnalysisIn):
    if not inp.query.strip():
        raise HTTPException(400, 'Query is required')
    for did in inp.dataset_ids:
        if not get_dataset(did):
            raise HTTPException(404, f'Dataset {did} is not available on this runtime instance. Re-select imagery from the library or re-upload it, then try again.')
    if not inp.dataset_ids:
        context = parse_query(inp.query, 0)
        if not context.get('can_auto_retrieve'):
            raise HTTPException(400, 'Select imagery, or ask a flood query containing a supported location and date range so SatQuery can retrieve Sentinel-1 automatically.')
    aid = 'an_' + uuid.uuid4().hex[:12]
    with db() as con:
        con.execute(
            'INSERT INTO analyses VALUES(?,?,?,?,?,?,?,?,?,?)',
            (aid, inp.query, json.dumps(inp.dataset_ids), 'queued', None, inp.provider, '[]', None, now(), None),
        )
    run_analysis(aid)
    row = get_analysis(aid)
    if not row:
        raise HTTPException(500, 'Analysis missing after execution')
    result = json.loads(row['result_json'] or '{}')
    result['analysis_id'] = aid
    result['status'] = row['status']
    result['events'] = json.loads(row['events_json'] or '[]')
    overlay = RESULTS / f'{aid}_overlay.png'
    if overlay.exists():
        result['overlay_b64'] = 'data:image/png;base64,' + base64.b64encode(overlay.read_bytes()).decode('ascii')
    return result


@app.get('/api/v1/analyses/{aid}/status')
def analysis_status(aid: str):
    row = get_analysis(aid)
    if not row:
        raise HTTPException(404, 'Analysis not found')
    return {
        'analysis_id': aid,
        'status': row['status'],
        'intent': row['intent'],
        'provider': row['provider'],
        'events': json.loads(row['events_json'] or '[]'),
    }


@app.get('/api/v1/analyses/{aid}/result')
def analysis_result(aid: str):
    row = get_analysis(aid)
    if not row:
        raise HTTPException(404, 'Analysis not found')
    if row['status'] not in ('completed', 'failed'):
        return JSONResponse({'status': row['status']}, status_code=202)
    result = json.loads(row['result_json'] or '{}')
    result['events'] = json.loads(row['events_json'] or '[]')
    return result


@app.get('/api/v1/analyses/{aid}/overlay')
def analysis_overlay(aid: str):
    p = RESULTS / f'{aid}_overlay.png'
    if not p.exists():
        raise HTTPException(404, 'Overlay not ready')
    return FileResponse(p, media_type='image/png')


@app.get('/api/v1/analyses/{aid}/geojson')
def analysis_geojson(aid: str):
    row = get_analysis(aid)
    if not row or not row['result_json']:
        raise HTTPException(404, 'Result not found')
    result = json.loads(row['result_json'])
    return result.get('geojson', {'type': 'FeatureCollection', 'features': []})


@app.get('/api/v1/analyses')
def list_analyses():
    with db() as con:
        rows = con.execute('SELECT * FROM analyses ORDER BY created_at DESC LIMIT 50').fetchall()
    return [
        {'id': r['id'], 'query': r['query'], 'status': r['status'], 'intent': r['intent'], 'provider': r['provider'], 'created_at': r['created_at']}
        for r in rows
    ]


@app.post('/api/v1/demo/load')
def load_demo():
    # Remove the old incorrectly geolocated Assam sample if it exists.
    with db() as con:
        legacy = con.execute("SELECT * FROM datasets WHERE filename='Assam_S1_SAR_flood.tif'").fetchall()
        for r in legacy:
            Path(r['path']).unlink(missing_ok=True)
            Path(r['preview_path']).unlink(missing_ok=True)
            con.execute('DELETE FROM datasets WHERE id=?', (r['id'],))
    samples = []
    for fname, mod, kind in DEMO_SPECS:
        existing = _demo_registered(fname)
        if existing:
            samples.append(dataset_row(existing))
            continue
        samples.append(_register_demo_file(fname, mod, kind))
    return samples
