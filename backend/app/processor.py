from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .flood_model import model_status
from .tool_registry import availability


_VISION_PRECEDENCE = ['vision.vqa_gemini', 'vision.clip_local', 'vision.vqa_eo_vlm', 'vision.image_statistics']
_FUSION_PRECEDENCE = ['fusion.multimodal_terramind', 'vision.vqa_eo_vlm', 'vision.clip_local', 'vision.image_statistics']
_SEGMENT_PRECEDENCE = ['segmentation.text_prompt_samgeo', 'vision.clip_local', 'vision.image_statistics']


def _row_meta(row: Any) -> Dict[str, Any]:
    try:
        raw = row['metadata_json']
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return dict((row or {}).get('metadata') or {})


def _row_modality(row: Any) -> str:
    try:
        return (row['modality'] or '').lower()
    except Exception:
        return str((row or {}).get('modality') or '').lower()


def alignment_provider(meta_a: Dict[str, Any], meta_b: Dict[str, Any]) -> Dict[str, Any]:
    geo_a = bool(meta_a.get('crs') and meta_a.get('transform'))
    geo_b = bool(meta_b.get('crs') and meta_b.get('transform'))
    if geo_a and geo_b:
        return {
            'name': 'geospatial_reprojection',
            'geospatial': True,
            'detail': 'Co-registration via rasterio reprojection onto the reference scene grid.',
        }
    return {
        'name': 'pixel_grid_alignment',
        'geospatial': False,
        'detail': 'Pixel-grid resizing used; full geospatial alignment unavailable because not both inputs carry CRS + transform.',
    }


def _first_enabled(precedence: List[str], av: Dict[str, Dict[str, Any]]) -> str:
    for name in precedence:
        if av.get(name, {}).get('enabled', False):
            return name
    return precedence[-1]


_METHOD_TOOL: Dict[str, str] = {
    'aligned_absdiff_otsu_polygonize': 'change.aligned_absdiff_otsu',
    'temporal_sar_water_change_with_persistent_water_suppression': 'flood.temporal_sar_change',
    'adaptive_dualpol_sar': 'flood.sar_adaptive_dualpol',
    'optical_water_heuristic': 'flood.single_scene',
    'image_statistics': 'vision.image_statistics',
}
_MODEL_TOOL: Dict[str, str] = {
    'Sentinel Flood Mapper': 'flood.sar_water_model',
    'Open-CD': 'change.trained_open_cd',
    'gemini': 'vision.vqa_gemini',
    'CLIP': 'vision.clip_local',
    'TEOChat': 'vision.vqa_eo_vlm',
    'SARChat': 'vision.vqa_eo_vlm',
    'LRS-VQA': 'vision.vqa_eo_vlm',
    'TerraMind': 'fusion.multimodal_terramind',
    'segment-geospatial': 'segmentation.text_prompt_samgeo',
}


def _executed_tool(intent: str, result: Dict[str, Any]) -> Optional[str]:
    method = str(result.get('method') or '')
    for key, tool in _METHOD_TOOL.items():
        if key in method:
            return tool
    info = result.get('model_info') or {}
    model = str((info if isinstance(info, dict) else {}).get('model') or (info if isinstance(info, dict) else {}).get('model_name') or '')
    for key, tool in _MODEL_TOOL.items():
        if key.lower() in model.lower():
            return tool
    if intent == 'flood_detection':
        return 'flood.single_scene'
    if intent in ('change_detection',):
        return 'change.aligned_absdiff_otsu'
    if intent in ('vegetation_change',):
        return 'vegetation.index_change'
    if 'ndvi' in method or 'greengreen' in method or 'excessgreen' in method.lower():
        return 'vegetation.index_change'
    if intent in ('vision_question', 'image_summary'):
        return 'vision.image_statistics'
    return None


def execution_evidence(plan: Dict[str, Any], pipeline: Dict[str, Any], result: Dict[str, Any], intent: str) -> Dict[str, Any]:
    intended = pipeline.get('intended_providers') or {}
    planned = list(plan.get('tools') or [])
    executed = _executed_tool(intent, result)

    executed_list: List[Dict[str, Any]] = []
    if executed:
        info = result.get('model_info') or {}
        info = info if isinstance(info, dict) else {}
        executed_list.append({
            'tool': executed,
            'model': str(info.get('model') or info.get('model_name') or result.get('method') or ''),
            'model_backed': bool(info.get('model_backed') is True or result.get('model_info', {}).get('model_backed') is True),
            'confidence': result.get('confidence'),
            'confidence_type': result.get('confidence_type'),
            'fallback': "satquery.inputs.user_upload" if not executed else None,
        })

    deviations: List[str] = []
    if executed and intended.get('vision') and executed == 'vision.image_statistics' and intended['vision'] != 'vision.image_statistics':
        deviations.append('Intended {0} but ran the local image-statistics baseline (no vision specialist connected).'.format(intended['vision']))
    if executed and intended.get('water') and executed == 'flood.sar_adaptive_dualpol' and intended['water'] != executed:
        deviations.append('Intended {0} but the trained flood checkpoint is not installed.'.format(intended['water']))
    if executed and intended.get('change') and executed == 'change.aligned_absdiff_otsu' and intended['change'] != executed:
        deviations.append('Intended {0} but the Open-CD service is offline.'.format(intended['change']))

    return {
        'planned': planned,
        'executed': executed_list,
        'deviations': deviations,
        'note': 'Planned tools come from the query planner; executed records are mapped back from the result method/model_info. Deviations are honest fallbacks, not hidden processing.',
    }


def build_pipeline(query_context: Dict[str, Any], datasets: List[Any]) -> Dict[str, Any]:
    """Plan-time pipeline/provider selection.

    This is a plan-time hint computed from configuration (env vars, checkpoint
    presence). run_analysis still performs the actual runtime routing and can
    fall back; the selection here is what the plan intends to run.
    """
    av = availability(model_status())
    metas = [_row_meta(d) for d in (datasets or [])]
    mods = [_row_modality(d) for d in (datasets or [])]
    intent = str(query_context.get('intent') or 'unsupported')
    temporal = bool(query_context.get('temporal'))

    alignment = None
    if len(datasets) >= 2:
        alignment = alignment_provider(metas[0], metas[1])

    intended: Dict[str, str] = {
        'water': 'flood.sar_water_model' if av['flood.sar_water_model']['enabled'] else 'flood.sar_adaptive_dualpol',
        'change': 'change.trained_open_cd' if av['change.trained_open_cd']['enabled'] else 'change.aligned_absdiff_otsu',
        'vegetation': 'vegetation.index_change',
        'vision': _first_enabled(_VISION_PRECEDENCE, av),
        'fusion': _first_enabled(_FUSION_PRECEDENCE, av),
        'segmentation': _first_enabled(_SEGMENT_PRECEDENCE, av),
    }

    return {
        'intent': intent,
        'temporal': temporal,
        'sensor_preference': query_context.get('preferred_sensor'),
        'inputs': {
            'count': len(datasets),
            'modalities': mods,
            'all_georeferenced': bool(metas) and all(bool(m.get('crs') and m.get('transform')) for m in metas),
        },
        'alignment': alignment,
        'intended_providers': intended,
        'note': 'Plan-time provider selection from configuration; runtime routing in run_analysis may fall back based on live specialist responses.',
    }