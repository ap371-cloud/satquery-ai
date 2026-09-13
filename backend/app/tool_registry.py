from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from . import geo_tools
from .satellite_catalog import retrieve_sentinel1_pair


def _t(**kw: Any) -> Dict[str, Any]:
    return kw


TOOLS: List[Dict[str, Any]] = [
    _t(
        name='satquery.retrieve.sentinel1_pair',
        title='Sentinel-1 RTC pair retrieval',
        description='Search Microsoft Planetary Computer for dual-polarisation (VV+VH) Sentinel-1 RTC scenes over the AOI for two time periods, convert backscatter to dB, and register both scenes as datasets.',
        category='retrieval',
        sensor='sar',
        temporal=True,
        inputs=['query_context (AOI + two periods)'],
        outputs=['2 SAR datasets (VV+VH, GeoTIFF, dB)'],
        model='Sentinel-1 RTC (no ML)',
        model_backed=False,
        gated_by=None,
        requires='Network access to Planetary Computer; pystac-client + planetary-computer installed',
        limitations=['Requires two explicit time periods in the query.', 'Dual-pol IW scenes only; AOI intersection must span at least 2 source pixels.'],
        fallback='satquery.inputs.user_upload',
        parameters=[
            {'name': 'bbox', 'type': 'list[float]', 'default': 'location.analysis_bbox', 'describe': 'AOI western/southern/eastern/northern bounds'},
            {'name': 'period_1', 'type': 'object', 'default': 'date_range.periods[0]', 'describe': 'Before period label+range'},
            {'name': 'period_2', 'type': 'object', 'default': 'date_range.periods[-1]', 'describe': 'After period label+range'},
        ],
    ),
    _t(
        name='satquery.inputs.user_upload',
        title='User-supplied imagery',
        description='User uploads or selects GeoTIFF/PNG/JPEG scenes from the dataset library.',
        category='retrieval',
        sensor='any',
        temporal=False,
        inputs=['uploaded files'],
        outputs=['datasets (optical or SAR)'],
        model='None',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['Georeferencing quality depends on the source file; un-georeferenced PNG uses pixel-grid alignment.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='geospatial.co_registration',
        title='Geospatial co-registration (optical/visual)',
        description='Align a second scene to the first using rasterio reprojection when both are georeferenced, falling back to pixel-grid resizing.',
        category='preprocess',
        sensor='any',
        temporal=True,
        inputs=['2 rasters'],
        outputs=['aligned arrays (reference georeferencing)', 'warnings'],
        model='None (deterministic reprojection)',
        model_backed=False,
        gated_by=None,
        requires='Both inputs carry CRS+transform when full alignment is wanted',
        limitations=['Visual alignment of largely different extents shrinks the common view.', 'Un-georeferenced inputs only get pixel-grid alignment.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='geospatial.co_registration_sar',
        title='Dual-pol SAR co-registration',
        description='Align before/after VV+VH SAR scenes to the first scene using reprojection; the after overlay is reprojected too.',
        category='preprocess',
        sensor='sar',
        temporal=True,
        inputs=['2 SAR rasters (VV+VH)'],
        outputs=['aligned SAR arrays', 'after RGB overlay', 'warnings'],
        model='None (deterministic reprojection)',
        model_backed=False,
        gated_by=None,
        requires='Both inputs carry CRS+transform when full alignment is wanted',
        limitations=['Same grid requirement as geospatial.co_registration.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='change.aligned_absdiff_otsu',
        title='Aligned image-difference change detection',
        description='Aligned grayscale absolute difference with Otsu thresholding, morphological cleaning, polygonisation and UTM area estimation.',
        category='analysis',
        sensor='any',
        temporal=True,
        inputs=['2 aligned rasters'],
        outputs=['overlay PNG', 'GeoJSON features', 'change_percent', 'changed_area_km2', 'confidence'],
        model='None (deterministic baseline)',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['A baseline comparator; not a trained change model.', 'Scene-level differences (sensor gain, clouds) can inflate the difference mask.'],
        fallback='change.trained_open_cd',
        parameters=[],
    ),
    _t(
        name='change.trained_open_cd',
        title='Trained Open-CD change mask',
        description='Predict a binary change mask with an Open-CD model exposed at OPENCD_URL, then polygonise and measure it.',
        category='analysis',
        sensor='optical',
        temporal=True,
        inputs=['2 aligned rasters'],
        outputs=['binary change mask', 'GeoJSON features', 'change_percent', 'changed_area_km2', 'confidence'],
        model='Open-CD (trained change detection)',
        model_backed=True,
        gated_by='OPENCD_URL',
        requires='OPENCD_URL pointing at a running scripts/opencd_bridge.py service',
        limitations=['Only available when the Open-CD bridge is connected.'],
        fallback='change.aligned_absdiff_otsu',
        parameters=[],
    ),
    _t(
        name='flood.sar_water_model',
        title='Sentinel Flood Mapper U-Net (SAR water)',
        description='Predict a water mask from VV+VH backscatter using the Sentinel Flood Mapper U-Net (EfficientNet-B0, tiled inference) when the checkpoint is installed.',
        category='analysis',
        sensor='sar',
        temporal=False,
        inputs=['SAR raster (VV+VH)'],
        outputs=['water mask', 'probability map', 'mean_probability'],
        model='Sentinel Flood Mapper U-Net EfficientNet-B0',
        model_backed=True,
        gated_by='flood_model',
        requires='SATQUERY_FLOOD_MODEL_PATH checkpoint + torch + segmentation-models-pytorch',
        limitations=['Requires the trained checkpoint and GPU/CPU model deps.', 'VV+VH two-band input only.'],
        fallback='flood.sar_adaptive_dualpol',
        parameters=[],
    ),
    _t(
        name='flood.sar_adaptive_dualpol',
        title='Adaptive dual-pol SAR water mask',
        description='Deterministic adaptive VV/VH dB-threshold water detector used when the trained checkpoint is not installed.',
        category='analysis',
        sensor='sar',
        temporal=False,
        inputs=['SAR raster (VV+VH, dB or linear)'],
        outputs=['water mask', 'thresholds', 'separation_db'],
        model='adaptive_dualpol_sar',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['Physics-based heuristic, not a trained model.', 'Needs physically plausible dB caps; extreme conditions can shift thresholds.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='flood.temporal_sar_change',
        title='Temporal SAR flood change',
        description='Two SAR water masks are differenced with persistent-water suppression: water in both periods stays persistent, new after-period water is probable inundation, and receded water is mapped separately.',
        category='analysis',
        sensor='sar',
        temporal=True,
        inputs=['2 aligned SAR rasters'],
        outputs=['overlay PNG (3-class legend)', 'probable_new GeoJSON', 'before/after/extent statistics', 'confidence'],
        model='Sentinel Flood Mapper or adaptive fallback',
        model_backed=False,
        gated_by=None,
        requires='Two overlapping SAR scenes',
        limitations=['New-flood extent excludes persistent water by design.', 'Mask quality follows the chosen SAR water tool.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='flood.single_scene',
        title='Single-scene water/flood footprint',
        description='Water-footprint detection on one scene: SAR uses the dual-pol detector/model, optical uses a blue-dominance heuristic.',
        category='analysis',
        sensor='any',
        temporal=False,
        inputs=['1 raster'],
        outputs=['overlay PNG', 'GeoJSON features', 'water_or_flood_percent', 'affected_area_km2'],
        model='model-backed SAR or optical heuristic',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['Single-image water is not equivalent to temporal flood mapping.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='vegetation.index_change',
        title='Vegetation index temporal change',
        description='NDVI (b4/b3) when NIR is available, else ExcessGreen; loss = fall below an adaptive percentile threshold, polygonised and measured.',
        category='analysis',
        sensor='optical',
        temporal=True,
        inputs=['2 aligned rasters'],
        outputs=['overlay PNG', 'GeoJSON features', 'vegetation_loss_percent', 'loss_area_km2'],
        model='None (deterministic index)',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['RGB-only inputs use ExcessGreen, which is scene-relative.', 'Seasonal phenology can appear as loss.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='vision.vqa_gemini',
        title='Gemini vision-language analysis (free tier)',
        description='Online remote-sensing VQA over the preview JPEGs when GEMINI_API_KEY is set.',
        category='vision',
        sensor='any',
        temporal=True,
        inputs=['1-2 images'],
        outputs=['semantic answer'],
        model='gemini-3.6-flash',
        model_backed=True,
        gated_by='GEMINI_API_KEY',
        requires='GEMINI_API_KEY (Google AI Studio, free)',
        limitations=['Answers are qualitative; numeric measurements come from the raster engine.', 'Two-image limit for temporal questions.'],
        fallback='vision.clip_local',
        parameters=[],
    ),
    _t(
        name='vision.vqa_eo_vlm',
        title='Remote-sensing EO VLM (TEOChat/SARChat/LRS-VQA bridges)',
        description='HTTP specialist services that run a real EO VLM and preprocess GeoTIFFs themselves; SAR semantics are refused when no SAR-specialised model is connected.',
        category='vision',
        sensor='any',
        temporal=True,
        inputs=['GeoTIFF bytes or previews'],
        outputs=['semantic answer', 'model metadata'],
        model='TEOChat/SARChat/LRS-VQA (per service)',
        model_backed=True,
        gated_by='TEOCHAT_URL',
        requires='TEOCHAT_URL (or SARCHAT_URL/LRSVQA_URL)',
        limitations=['Depends on which bridge is configured.', 'SAR-domain questions need a SAR-specialised service.'],
        fallback='vision.clip_local',
        parameters=[],
    ),
    _t(
        name='vision.clip_local',
        title='On-container CLIP zero-shot scene analysis',
        description='Free keyless closed-set scene/water/vegetation/building classification with real model confidences using a baked CLIP ViT-B/32.',
        category='vision',
        sensor='any',
        temporal=False,
        inputs=['1 image'],
        outputs=['top-label classification with confidence'],
        model='CLIP ViT-B/32 (local)',
        model_backed=True,
        gated_by='clip_model',
        requires='CLIP_MODEL_DIR containing a local CLIP checkpoint',
        limitations=['Closed-set labels only; not a free-form visual language model.'],
        fallback='vision.image_statistics',
        parameters=[],
    ),
    _t(
        name='vision.image_statistics',
        title='Local image-statistics baseline',
        description='Deterministic brightness/green/blue coverage summary used when no vision specialist is available. Never presented as a semantic VLM.',
        category='vision',
        sensor='any',
        temporal=False,
        inputs=['1 raster'],
        outputs=['mean_brightness', 'green_dominant_percent', 'blue_dominant_percent'],
        model='None (deterministic)',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['Not semantic interpretation.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='segmentation.text_prompt_samgeo',
        title='Text-prompt geospatial segmentation (SAM-GEO)',
        description='Segment an object class named in the query into geospatial polygons via the segment-geospatial API.',
        category='analysis',
        sensor='optical',
        temporal=False,
        inputs=['1 raster', 'text prompt'],
        outputs=['GeoJSON features', 'detected_object_count', 'detected_area_km2'],
        model='segment-geospatial/SAM text segmentation',
        model_backed=True,
        gated_by='SAMGEO_URL',
        requires='SAMGEO_URL pointing at a running SAM-GEO REST API',
        limitations=['Only available when the SAM-GEO service is connected.', 'Pixel grounding quality depends on the prompt.'],
        fallback='vision.clip_local',
        parameters=[],
    ),
    _t(
        name='fusion.multimodal_terramind',
        title='Optical + SAR multimodal fusion (TerraMind/TerraTorch)',
        description='Feature-level multimodal EO fusion over aligned optical + SAR inputs when a TERRAMIND_URL task service is configured.',
        category='fusion',
        sensor='optical+sar',
        temporal=False,
        inputs=['1 optical raster', '1 SAR raster', 'query'],
        outputs=['structured task result / semantic summary'],
        model='TerraMind/TerraTorch',
        model_backed=True,
        gated_by='TERRAMIND_URL',
        requires='TERRAMIND_URL with a task-specific downstream head',
        limitations=['Requires selecting/fine-tuning a downstream task head for production.', 'Feature-level fusion only when the service is connected.'],
        fallback='vision.vqa_eo_vlm',
        parameters=[],
    ),
    _t(
        name='evidence.polygonize_area',
        title='Mask → GeoJSON + UTM area',
        description='Vectorise a binary mask into GeoJSON features (max 120), compute true area via a local UTM projection, and drop sub-pixel slivers.',
        category='evidence',
        sensor='any',
        temporal=False,
        inputs=['binary mask', 'raster georeferencing'],
        outputs=['FeatureCollection (area_m2 per feature)', 'total_area_m2'],
        model='None (deterministic)',
        model_backed=False,
        gated_by=None,
        requires='CRS + transform on the source raster for true areas',
        limitations=['Un-georeferenced rasters cannot yield real-world areas.'],
        fallback=None,
        parameters=[],
    ),
    _t(
        name='lm.intent',
        title='Natural-language intent & context parser',
        description='Deterministic parser extracting intent, location (gazetteer/Nominatim), date range, sensor preference, and target object from the query.',
        category='planning',
        sensor='any',
        temporal=False,
        inputs=['query text'],
        outputs=['query_context'],
        model='None (deterministic rules)',
        model_backed=False,
        gated_by=None,
        requires='None',
        limitations=['Rule-based; unusual phrasing may need a synonym or an explicit upload.'],
        fallback=None,
        parameters=[],
    ),
]


_FNS: Dict[str, Callable] = {
    'satquery.retrieve.sentinel1_pair': retrieve_sentinel1_pair,
    'geospatial.co_registration': geo_tools._align_second_to_first,
    'geospatial.co_registration_sar': geo_tools._align_sar_pair,
    'change.aligned_absdiff_otsu': geo_tools.change_detection,
    'flood.sar_water_model': geo_tools._sar_mask,
    'flood.sar_adaptive_dualpol': geo_tools._adaptive_sar_water_mask,
    'flood.temporal_sar_change': geo_tools.temporal_flood_detection,
    'flood.single_scene': geo_tools.flood_detection,
    'vegetation.index_change': geo_tools.vegetation_change,
    'vision.image_statistics': geo_tools.summarize_image,
    'evidence.polygonize_area': geo_tools._area,
}


def find_tool(name: str) -> Dict[str, Any]:
    for tool in TOOLS:
        if tool['name'] == name:
            return tool
    raise KeyError(f'Tool {name!r} is not registered.')


def describe(name: str) -> Dict[str, Any]:
    tool = dict(find_tool(name))
    tool.pop('fn', None)
    return tool


def all_tools() -> List[Dict[str, Any]]:
    return [describe(t['name']) for t in TOOLS]


def _clip_present() -> bool:
    import pathlib

    root = pathlib.Path(os.getenv('CLIP_MODEL_DIR', '/app/models/clip'))
    if not root.exists() or (root / '.missing').exists():
        return False
    return (root / 'config.json').exists()


def availability(flood_status: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    flood_ready = bool(flood_status and flood_status.get('ready'))
    for tool in TOOLS:
        gate = tool.get('gated_by')
        if gate == 'flood_model':
            enabled, reason = flood_ready, ('flood checkpoint present' if flood_ready else 'flood checkpoint/deps not installed')
        elif gate == 'clip_model':
            enabled, reason = _clip_present(), ('CLIP baked' if _clip_present() else 'CLIP not baked (CLIP_MODEL_DIR config required)')
        elif gate:
            enabled, reason = bool(os.getenv(gate)), f'{gate} set'
        else:
            enabled, reason = True, 'always available'
        out[tool['name']] = {
            'enabled': enabled,
            'reason': reason,
            'category': tool['category'],
            'sensor': tool['sensor'],
            'temporal': tool['temporal'],
            'model_backed': tool['model_backed'],
            'fallback': tool.get('fallback'),
        }
    return out