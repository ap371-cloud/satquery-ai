from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import geo_tools
from .tool_registry import find_tool


def _step(step: int, tool: str, purpose: str, outputs: List[str], risk: Optional[str] = None) -> Dict[str, Any]:
    meta = find_tool(tool)
    return {
        'step': step,
        'tool': tool,
        'title': meta['title'],
        'category': meta['category'],
        'purpose': purpose,
        'inputs': meta['inputs'],
        'expected_output': outputs or meta['outputs'],
        'risk': risk,
        'fallback': meta.get('fallback'),
    }


def _precondition(name: str, satisfied: bool, detail: str) -> Dict[str, Any]:
    return {'name': name, 'satisfied': bool(satisfied), 'detail': detail}


def _overlap_checked(datasets: List[Any]) -> Dict[str, Any]:
    if len(datasets) < 2:
        return {'checked': False, 'compatible': None, 'overlap_ratio': None, 'warnings': []}
    first, second = datasets[0], datasets[1]
    try:
        comp = geo_tools.compatibility(first['path'], second['path'])
    except Exception as exc:
        return {'checked': False, 'compatible': None, 'overlap_ratio': None, 'warnings': [str(exc)]}
    return {'checked': True, **comp}


def build_plan(query_context: Dict[str, Any], datasets: List[Any]) -> Dict[str, Any]:
    """Build a structured, persisted tool plan for a parsed query.

    The plan is derived deterministically from the parsed query context and the
    selected datasets. Preconditions are evaluated against real raster metadata
    (overlap, modality, count) so the plan never claims a harder step than the
    inputs can support. It is a plan, not an execution trace: run_analysis still
    owns the actual tool routing and can fall back at runtime.
    """
    intent = str(query_context.get('intent') or 'unsupported')
    unsupported = query_context.get('supported') is False or intent == 'unsupported'
    loc = query_context.get('location') or {}
    dr = query_context.get('date_range') or {}
    can_auto = bool(query_context.get('can_auto_retrieve'))
    temporal = bool(query_context.get('temporal'))
    n = len(datasets or [])
    sar_count = sum(1 for _ in (datasets or []) if (_ is not None) and str(getattr(_, 'get', lambda k, d=None: d)('modality', '') or '').lower() == 'sar')
    use_rows = (datasets or [])[:2]

    needs_pair = (
        intent in {'change_detection', 'vegetation_change'}
        or (intent == 'flood_detection' and temporal)
        or (intent == 'multimodal_fusion' and n >= 1)
    )
    pair_ok = n >= 2
    if intent == 'flood_detection' and temporal:
        pair_ok = n >= 2 and sar_count >= 2
    overlap = _overlap_checked(use_rows)
    pair_compatible = not overlap['checked'] or bool(overlap.get('compatible'))

    steps: List[Dict[str, Any]] = []
    preconditions: List[Dict[str, Any]] = []

    if unsupported:
        return {
            'summary': 'The request does not match a supported Earth-observation capability.',
            'unsupported': True,
            'unsupported_reason': query_context.get('unsupported_reason'),
            'preconditions': [],
            'steps': [],
            'tools': [],
        }

    steps.append(_step(1, 'lm.intent', 'Interpret the query into intent, AOI, date range, sensor and target object.', ['query_context']))

    if not datasets and can_auto:
        steps.append(_step(2, 'satquery.retrieve.sentinel1_pair', f"Retrieve Sentinel-1 RTC before/after scenes for {loc.get('name') or 'the resolved AOI'} ({dr.get('start_date')} to {dr.get('end_date')}).", ['2 SAR datasets'], risk=None))
    else:
        steps.append(_step(2, 'satquery.inputs.user_upload', 'Use the selected imagery as analysis inputs.', ['datasets'], risk=('No resolvable AOI/date range for automatic retrieval' if not datasets else None)))

    if needs_pair:
        preconditions.append(_precondition(
            'temporal_pair',
            pair_ok,
            ('Two overlapping SAR scenes are required for temporal flood mapping.' if intent == 'flood_detection' else 'Two overlapping scenes are required for this temporal analysis.') if not pair_ok else 'Two overlapping scenes are available.'
        ))
        if not pair_ok:
            steps.append(_step(2, 'satquery.retrieve.sentinel1_pair' if can_auto else 'satquery.inputs.user_upload', 'Obtain the missing second scene.', ['second dataset'], risk='pair incomplete'))
        if pair_ok:
            if intent in {'flood_detection', 'change_detection', 'vegetation_change'} or (intent == 'multimodal_fusion' and sar_count >= 2):
                tool = 'geospatial.co_registration_sar' if intent == 'flood_detection' else 'geospatial.co_registration'
                steps.append(_step(3, tool, 'Align the two scenes onto a common grid so pixel-level comparison is valid.', ['aligned arrays'], risk=None if pair_compatible else 'scenes may not overlap'))
            preconditions.append(_precondition(
                'overlap',
                pair_compatible,
                ('No spatial overlap detected between the selected scenes.' if overlap['checked'] and not overlap['compatible'] else 'Scenes overlap (or overlap could not be verified).')
            ))

    if intent == 'flood_detection':
        if temporal and pair_ok:
            steps.append(_step(4, 'flood.sar_water_model', 'Classify water in each SAR scene (trained checkpoint when installed; adaptive dual-pol otherwise).', ['2 water masks'], risk='adaptive fallback when the checkpoint is absent'))
            steps.append(_step(5, 'flood.temporal_sar_change', 'Compute before/after water change with persistent-water suppression and map probable new inundation.', ['overlay', 'GeoJSON', 'statistics', 'confidence'], risk=None))
        else:
            steps.append(_step(3, 'flood.single_scene', 'Detect a water/flood footprint in the single scene.', ['overlay', 'GeoJSON', 'statistics'], risk='single-image water is not temporal flood mapping'))
    elif intent == 'change_detection':
        steps.append(_step(4, 'change.trained_open_cd', 'Predict a change mask with the trained Open-CD specialist when connected.', ['binary mask'], risk=None))
        steps.append(_step(5, 'change.aligned_absdiff_otsu', 'Compute the aligned difference baseline (or consume the trained mask) and measure change.', ['overlay', 'GeoJSON', 'statistics', 'confidence'], risk='trained specialist offline -> deterministic baseline'))
    elif intent == 'vegetation_change':
        steps.append(_step(4, 'vegetation.index_change', 'Compute NDVI (or ExcessGreen fallback) per scene, take the temporal loss, and polygonise it.', ['overlay', 'GeoJSON', 'statistics', 'confidence'], risk=None))
    elif intent == 'multimodal_fusion':
        steps.append(_step(3, 'geospatial.co_registration', 'Align the optical and SAR scenes onto a common grid.', ['aligned arrays'], risk=None if pair_compatible else 'scenes may not overlap'))
        steps.append(_step(4, 'fusion.multimodal_terramind', 'Fuse optical + SAR features (TerraMind) when the task service is connected.', ['structured result / summary'], risk='feature-level fusion unavailable -> semantic cross-modal fallback'))
    elif intent == 'grounded_segmentation':
        steps.append(_step(3, 'segmentation.text_prompt_samgeo', f"Segment '{query_context.get('target_object') or 'target object'}' into geospatial polygons.", ['GeoJSON', 'count', 'area'], risk='segmentation service offline -> semantic VQA fallback'))
    elif intent in ('vision_question', 'image_summary'):
        steps.append(_step(3, 'vision.vqa_gemini', 'Ask a remote-sensing vision model about the scene(s).', ['semantic answer'], risk='no vision specialist -> local image statistics baseline'))
    else:
        steps.append(_step(3, 'vision.image_statistics', 'Produce the local image-statistics summary.', ['statistics'], risk=None))

    steps.append(_step(len(steps) + 1, 'evidence.polygonize_area', 'Vectorise any binary mask into GeoJSON and compute UTM-backed areas.', ['FeatureCollection', 'total_area_m2'], risk='no true area without CRS'))

    tools_used: List[str] = []
    for s in steps:
        if s['tool'] not in tools_used:
            tools_used.append(s['tool'])

    return {
        'summary': f"Intent '{intent}' over {n} dataset(s): {'; '.join(s['title'] for s in steps)}.",
        'unsupported': False,
        'intent': intent,
        'preconditions': preconditions,
        'steps': steps,
        'tools': tools_used,
        'sensor_preference': query_context.get('preferred_sensor'),
        'temporal': temporal,
        'aoi': {
            'name': loc.get('name'),
            'bbox_wgs84': loc.get('bbox') or loc.get('analysis_bbox'),
            'source': loc.get('source'),
        },
    }