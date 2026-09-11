from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.warp import reproject, transform_bounds
from shapely.geometry import shape, mapping
from shapely.ops import transform as shp_transform
from pyproj import CRS, Transformer

from .flood_model import predict_water, model_status


def _stretch(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    good = np.isfinite(arr)
    if not good.any():
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(arr[good], [2, 98])
    if hi <= lo:
        hi = lo + 1.0
    arr = np.clip((arr - lo) / (hi - lo), 0, 1)
    return (arr * 255).astype(np.uint8)


def _bounds_wgs84(crs, bounds):
    if not crs or not bounds:
        return None
    try:
        if CRS.from_user_input(crs).to_epsg() == 4326:
            return [float(x) for x in bounds]
        return [float(x) for x in transform_bounds(crs, "EPSG:4326", *bounds, densify_pts=21)]
    except Exception:
        return None


def read_raster(path: str | Path) -> Dict[str, Any]:
    path = str(path)
    suffix = Path(path).suffix.lower()
    if suffix in {'.tif', '.tiff'}:
        with rasterio.open(path) as src:
            count = src.count
            data = src.read()
            bounds = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]
            tags = src.tags()
            meta = {
                'width': src.width,
                'height': src.height,
                'count': count,
                'crs': src.crs.to_string() if src.crs else None,
                'transform': tuple(src.transform)[:6],
                'bounds': bounds,
                'bounds_wgs84': _bounds_wgs84(src.crs, bounds),
                'dtype': str(src.dtypes[0]) if src.dtypes else None,
                'nodata': src.nodata,
                'resolution': [abs(src.transform.a), abs(src.transform.e)],
                'driver': src.driver,
                'band_descriptions': list(src.descriptions or []),
                'source': tags.get('source'),
                'stac_id': tags.get('stac_item'),
                'acquired_at': tags.get('acquired_at'),
                'location_name': tags.get('location_name'),
            }
            if count >= 3:
                rgb = np.stack([_stretch(data[0]), _stretch(data[1]), _stretch(data[2])], axis=-1)
            elif count == 2:
                # Useful VV / VH pseudo-colour composite for SAR.
                vv, vh = _stretch(data[0]), _stretch(data[1])
                ratio = _stretch(data[0].astype(np.float32) - data[1].astype(np.float32))
                rgb = np.stack([vv, vh, ratio], axis=-1)
            else:
                g = _stretch(data[0])
                rgb = np.stack([g, g, g], axis=-1)
            return {'data': data, 'rgb': rgb, 'meta': meta}

    img = Image.open(path).convert('RGB')
    rgb = np.array(img)
    data = np.transpose(rgb, (2, 0, 1))
    return {
        'data': data,
        'rgb': rgb,
        'meta': {
            'width': rgb.shape[1], 'height': rgb.shape[0], 'count': 3,
            'crs': None, 'transform': None, 'bounds': None, 'bounds_wgs84': None,
            'dtype': str(rgb.dtype), 'nodata': None,
            'resolution': None, 'driver': 'image', 'band_descriptions': [],
            'source': None, 'stac_id': None, 'acquired_at': None, 'location_name': None,
        }
    }


def make_preview(path: str | Path, out_path: str | Path) -> str:
    r = read_raster(path)
    Image.fromarray(r['rgb']).save(out_path)
    return str(out_path)


def _resize_rgb(rgb: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    return cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)


def _align_second_to_first(first_path: str | Path, second_path: str | Path) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any], List[str]]:
    a = read_raster(first_path)
    b = read_raster(second_path)
    warnings: List[str] = []
    meta = a['meta']

    if Path(first_path).suffix.lower() in {'.tif', '.tiff'} and Path(second_path).suffix.lower() in {'.tif', '.tiff'}:
        try:
            with rasterio.open(first_path) as ref, rasterio.open(second_path) as src:
                if ref.crs and src.crs:
                    src_rgb = b['rgb']
                    dst_rgb = np.zeros((ref.height, ref.width, 3), dtype=np.uint8)
                    for i in range(3):
                        reproject(
                            source=src_rgb[:, :, i], destination=dst_rgb[:, :, i],
                            src_transform=src.transform, src_crs=src.crs,
                            dst_transform=ref.transform, dst_crs=ref.crs,
                            resampling=Resampling.bilinear,
                        )
                    return a['rgb'], dst_rgb, meta, warnings
        except Exception as exc:
            warnings.append(f'Geospatial reprojection fallback used: {exc}')

    h, w = a['rgb'].shape[:2]
    warnings.append('Pixel-grid alignment used; exact geospatial alignment was unavailable.')
    return a['rgb'], _resize_rgb(b['rgb'], (w, h)), meta, warnings


def _align_sar_pair(first_path: str | Path, second_path: str | Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any], List[str]]:
    """Return before/after SAR arrays aligned to the first raster plus after RGB."""
    a = read_raster(first_path)
    b = read_raster(second_path)
    warnings: List[str] = []
    meta = a['meta']

    def two_bands(r):
        d = r['data'].astype(np.float32)
        if d.shape[0] >= 2:
            return d[:2]
        g = d[0]
        return np.stack([g, g], axis=0)

    aa = two_bands(a)
    bb = two_bands(b)

    if Path(first_path).suffix.lower() in {'.tif', '.tiff'} and Path(second_path).suffix.lower() in {'.tif', '.tiff'}:
        try:
            with rasterio.open(first_path) as ref, rasterio.open(second_path) as src:
                if ref.crs and src.crs:
                    dst = np.zeros((2, ref.height, ref.width), dtype=np.float32)
                    for i in range(2):
                        source_band = bb[min(i, bb.shape[0]-1)]
                        reproject(
                            source=source_band, destination=dst[i],
                            src_transform=src.transform, src_crs=src.crs,
                            dst_transform=ref.transform, dst_crs=ref.crs,
                            resampling=Resampling.bilinear,
                        )
                    after_rgb = np.zeros((ref.height, ref.width, 3), dtype=np.uint8)
                    src_rgb = b['rgb']
                    for i in range(3):
                        reproject(
                            source=src_rgb[:, :, i], destination=after_rgb[:, :, i],
                            src_transform=src.transform, src_crs=src.crs,
                            dst_transform=ref.transform, dst_crs=ref.crs,
                            resampling=Resampling.bilinear,
                        )
                    return aa, dst, after_rgb, meta, warnings
        except Exception as exc:
            warnings.append(f'SAR geospatial alignment fallback used: {exc}')

    h, w = aa.shape[1:]
    dst = np.stack([cv2.resize(bb[i], (w, h), interpolation=cv2.INTER_LINEAR) for i in range(2)], axis=0)
    warnings.append('SAR pixel-grid alignment used because full geospatial alignment was unavailable.')
    return aa, dst, _resize_rgb(b['rgb'], (w, h)), meta, warnings


def compatibility(first_path: str | Path, second_path: str | Path) -> Dict[str, Any]:
    a = read_raster(first_path)['meta']
    b = read_raster(second_path)['meta']
    warnings = []
    overlap = None
    if a['bounds_wgs84'] and b['bounds_wgs84']:
        al, ab, ar, at = a['bounds_wgs84']
        bl, bb, br, bt = b['bounds_wgs84']
        ix = max(0, min(ar, br) - max(al, bl))
        iy = max(0, min(at, bt) - max(ab, bb))
        inter = ix * iy
        area_a = max(1e-12, (ar-al)*(at-ab))
        overlap = inter / area_a
        if overlap <= 0:
            warnings.append('No spatial overlap detected.')
    elif a['crs'] != b['crs']:
        warnings.append('CRS differs; reprojection will be attempted.')
    else:
        warnings.append('Geospatial overlap could not be verified for one or both inputs.')
    return {
        'compatible': overlap is None or overlap > 0,
        'same_crs': a['crs'] == b['crs'],
        'overlap_ratio': overlap,
        'same_size': a['width'] == b['width'] and a['height'] == b['height'],
        'warnings': warnings,
    }


def _clean_mask(mask: np.ndarray, iterations: int = 2) -> np.ndarray:
    mask = (mask > 0).astype(np.uint8) * 255
    k = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=iterations)
    return mask


def _overlay(rgb: np.ndarray, mask: np.ndarray, color=(255, 72, 80), alpha=0.55) -> np.ndarray:
    out = rgb.copy().astype(np.float32)
    m = mask > 0
    color_arr = np.array(color, dtype=np.float32)
    out[m] = out[m] * (1-alpha) + color_arr * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _multi_overlay(rgb: np.ndarray, layers: List[Tuple[np.ndarray, Tuple[int, int, int], float]]) -> np.ndarray:
    out = rgb.copy().astype(np.float32)
    for mask, color, alpha in layers:
        m = mask > 0
        c = np.array(color, dtype=np.float32)
        out[m] = out[m] * (1-alpha) + c * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _utm_transformer(meta: Dict[str, Any]):
    if not meta.get('crs') or not meta.get('bounds'):
        return None
    src_crs = CRS.from_user_input(meta['crs'])
    if src_crs.is_projected:
        return None
    l, b, r, t = meta['bounds']
    lon, lat = (l+r)/2, (b+t)/2
    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return Transformer.from_crs(src_crs, CRS.from_epsg(epsg), always_xy=True)


def _mask_geojson(mask: np.ndarray, meta: Dict[str, Any], max_features: int = 120, properties: Dict[str, Any] | None = None) -> Tuple[Dict[str, Any], float | None]:
    transform = meta.get('transform')
    crs = meta.get('crs')
    if not transform or not crs:
        return {'type': 'FeatureCollection', 'features': []}, None
    affine = rasterio.Affine(*transform)
    feats = []
    total_area_m2 = 0.0
    src_crs = CRS.from_user_input(crs)
    utm = _utm_transformer(meta)
    to_wgs = None if src_crs.to_epsg() == 4326 else Transformer.from_crs(src_crs, CRS.from_epsg(4326), always_xy=True)

    for geom, val in shapes((mask > 0).astype(np.uint8), mask=(mask > 0), transform=affine):
        if val != 1:
            continue
        g = shape(geom)
        try:
            if src_crs.is_projected:
                area = float(g.area)
            elif utm:
                area = float(shp_transform(utm.transform, g).area)
            else:
                area = 0.0
        except Exception:
            area = 0.0
        if area < 20.0:
            continue
        total_area_m2 += area
        if len(feats) < max_features:
            out_geom = shp_transform(to_wgs.transform, g) if to_wgs else g
            props = {'area_m2': round(area, 2), **(properties or {})}
            feats.append({'type': 'Feature', 'properties': props, 'geometry': mapping(out_geom)})
    return {'type': 'FeatureCollection', 'features': feats}, (total_area_m2 if total_area_m2 > 0 else None)


def _pixel_area_estimate(mask: np.ndarray, meta: Dict[str, Any]) -> float | None:
    if not meta.get('resolution') or not meta.get('crs'):
        return None
    crs = CRS.from_user_input(meta['crs'])
    if not crs.is_projected:
        return None
    px = float(meta['resolution'][0]) * float(meta['resolution'][1])
    return float((mask > 0).sum() * px)


def _area(mask: np.ndarray, meta: Dict[str, Any]) -> Tuple[Dict[str, Any], float | None]:
    gj, area_m2 = _mask_geojson(mask, meta)
    if area_m2 is None:
        area_m2 = _pixel_area_estimate(mask, meta)
    return gj, area_m2


def change_detection(first_path: str | Path, second_path: str | Path, out_path: str | Path) -> Dict[str, Any]:
    a, b, meta, warnings = _align_second_to_first(first_path, second_path)
    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    diff = cv2.absdiff(ga, gb)
    diff_blur = cv2.GaussianBlur(diff, (5,5), 0)
    otsu, mask = cv2.threshold(diff_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    floor = max(18, int(otsu))
    mask = _clean_mask((diff_blur >= floor).astype(np.uint8) * 255)
    overlay = _overlay(b, mask, color=(255, 72, 80))
    Image.fromarray(overlay).save(out_path)
    geojson, area_m2 = _area(mask, meta)
    pct = float((mask > 0).mean() * 100)
    signal = float(np.mean(diff[mask > 0])) if (mask > 0).any() else 0.0
    confidence = min(0.90, 0.55 + min(signal / 255.0, 0.28) + (0.07 if meta.get('crs') else 0))
    return {
        'overlay_path': str(out_path), 'geojson': geojson,
        'statistics': {'change_percent': round(pct, 2), 'changed_area_km2': round(area_m2/1e6, 4) if area_m2 else None},
        'confidence': round(confidence, 3), 'confidence_type': 'operational_heuristic',
        'warnings': warnings + ['Change detector is a deterministic aligned image-difference baseline; production accuracy should use a trained change model.'],
        'method': 'aligned_absdiff_otsu_polygonize', 'map_bounds_wgs84': meta.get('bounds_wgs84')
    }


def _adaptive_sar_water_mask(arr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Dual-pol adaptive water detector used only when the trained model is unavailable."""
    x = arr.astype(np.float32)
    if x.ndim != 3:
        raise ValueError('Expected C×H×W SAR array.')
    vv = x[0]
    vh = x[1] if x.shape[0] > 1 else x[0]

    def db(b):
        finite = b[np.isfinite(b)]
        if finite.size and float(np.nanpercentile(finite, 5)) >= 0:
            return 10 * np.log10(np.clip(b, 1e-8, None))
        return b

    vv, vh = db(vv), db(vh)
    vv = np.nan_to_num(vv, nan=np.nanmedian(vv[np.isfinite(vv)]) if np.isfinite(vv).any() else -10.0)
    vh = np.nan_to_num(vh, nan=np.nanmedian(vh[np.isfinite(vh)]) if np.isfinite(vh).any() else -17.0)
    vv_s = cv2.GaussianBlur(vv.astype(np.float32), (5,5), 0)
    vh_s = cv2.GaussianBlur(vh.astype(np.float32), (5,5), 0)

    # Adaptive thresholds with physically plausible dB caps.
    vv_thr = min(-15.0, float(np.percentile(vv_s, 30)))
    vh_thr = min(-21.0, float(np.percentile(vh_s, 32)))
    ratio = vv_s - vh_s
    candidate = (vv_s <= vv_thr) & (vh_s <= vh_thr) & (ratio >= 1.0)
    mask = _clean_mask(candidate.astype(np.uint8) * 255, iterations=1)
    separation = 0.0
    if (mask > 0).any() and (mask == 0).any():
        separation = abs(float(vv_s[mask > 0].mean()) - float(vv_s[mask == 0].mean()))
    return mask, {'vv_threshold_db': round(vv_thr, 2), 'vh_threshold_db': round(vh_thr, 2), 'separation_db': round(separation, 2), 'model_backed': False, 'model': 'adaptive_dualpol_sar'}


def _sar_mask(arr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    prediction = predict_water(arr)
    if prediction is not None:
        mask = prediction['mask']
        info = {k: v for k, v in prediction.items() if k not in ('mask', 'probabilities')}
        info['model_backed'] = bool(info.get('model_backed'))
        return _clean_mask(mask, iterations=1), info
    return _adaptive_sar_water_mask(arr)


def flood_detection(path: str | Path, out_path: str | Path, modality: str = 'auto') -> Dict[str, Any]:
    r = read_raster(path)
    rgb, meta, raw = r['rgb'], r['meta'], r['data']
    name = str(path).lower()
    sar = modality == 'sar' or 'sar' in name or 'sentinel-1' in name or raw.shape[0] == 2
    warnings = []
    if sar:
        mask, model_info = _sar_mask(raw)
        reason = 'SAR selected because radar is suitable for flood mapping under cloud cover.'
        if not model_info.get('model_backed'):
            warnings.append('Pretrained SAR flood model is not installed; adaptive dual-polarisation fallback was used. Run scripts/setup_flood_model.py --install-deps for model-backed inference.')
    else:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        arr = rgb.astype(np.int16)
        blue_dom = arr[:,:,2] - ((arr[:,:,0] + arr[:,:,1]) / 2)
        dark = gray < np.percentile(gray, 35)
        mask = np.logical_or(blue_dom > 10, dark & (arr[:,:,2] >= arr[:,:,0])).astype(np.uint8) * 255
        mask = _clean_mask(mask)
        model_info = {'model_backed': False, 'model': 'optical_water_heuristic'}
        reason = 'Optical water fallback selected because the input was not identified as SAR.'
        warnings.append('Optical single-image water output is not equivalent to temporal flood extent.')
    overlay = _overlay(rgb, mask, color=(34, 211, 238), alpha=0.58)
    Image.fromarray(overlay).save(out_path)
    geojson, area_m2 = _area(mask, meta)
    pct = float((mask > 0).mean() * 100)
    confidence = 0.88 if model_info.get('model_backed') else (0.72 if sar else 0.58)
    return {
        'overlay_path': str(out_path), 'geojson': geojson,
        'statistics': {'water_or_flood_percent': round(pct, 2), 'affected_area_km2': round(area_m2/1e6, 4) if area_m2 else None},
        'confidence': confidence, 'confidence_type': 'model_assisted' if model_info.get('model_backed') else 'operational_heuristic',
        'warnings': warnings,
        'method': model_info.get('model', 'sar_water'), 'routing_reason': reason,
        'model_info': model_info, 'map_bounds_wgs84': meta.get('bounds_wgs84')
    }


def temporal_flood_detection(before_path: str | Path, after_path: str | Path, out_path: str | Path) -> Dict[str, Any]:
    before, after, after_rgb, meta, warnings = _align_sar_pair(before_path, after_path)
    pre_mask, pre_info = _sar_mask(before)
    post_mask, post_info = _sar_mask(after)

    pre = pre_mask > 0
    post = post_mask > 0
    persistent = (pre & post).astype(np.uint8) * 255
    probable_new = ((~pre) & post).astype(np.uint8) * 255
    receded = (pre & (~post)).astype(np.uint8) * 255
    probable_new = _clean_mask(probable_new, iterations=1)
    persistent = _clean_mask(persistent, iterations=1)
    receded = _clean_mask(receded, iterations=1)

    # Persistent water is shown blue, new probable inundation bright cyan/red.
    overlay = _multi_overlay(after_rgb, [
        (persistent, (37, 99, 235), 0.42),
        (receded, (245, 158, 11), 0.42),
        (probable_new, (239, 68, 68), 0.72),
    ])
    Image.fromarray(overlay).save(out_path)

    geojson, flood_area = _mask_geojson(probable_new, meta, properties={'class': 'probable_new_inundation'})
    _, persistent_area = _mask_geojson(persistent, meta, properties={'class': 'persistent_water'})
    _, receded_area = _mask_geojson(receded, meta, properties={'class': 'receded_water'})
    if flood_area is None: flood_area = _pixel_area_estimate(probable_new, meta)
    if persistent_area is None: persistent_area = _pixel_area_estimate(persistent, meta)
    if receded_area is None: receded_area = _pixel_area_estimate(receded, meta)

    model_backed = bool(pre_info.get('model_backed') and post_info.get('model_backed'))
    if not model_backed:
        warnings.append('Temporal flood logic is real (post-water minus pre-existing water), but the SAR water masks are using the adaptive fallback until the pretrained checkpoint is installed.')
    confidence = 0.91 if model_backed else 0.79
    stats = {
        'before_water_percent': round(float(pre.mean() * 100), 2),
        'after_water_percent': round(float(post.mean() * 100), 2),
        'probable_new_flood_percent': round(float((probable_new > 0).mean() * 100), 2),
        'probable_flood_area_km2': round(flood_area / 1e6, 4) if flood_area else 0.0,
        'persistent_water_area_km2': round(persistent_area / 1e6, 4) if persistent_area else 0.0,
        'receded_water_area_km2': round(receded_area / 1e6, 4) if receded_area else 0.0,
    }
    return {
        'overlay_path': str(out_path), 'geojson': geojson, 'statistics': stats,
        'confidence': confidence, 'confidence_type': 'model_assisted_temporal' if model_backed else 'operational_temporal',
        'warnings': warnings,
        'method': 'temporal_sar_water_change_with_persistent_water_suppression',
        'routing_reason': 'Temporal flood analysis compares two SAR water masks; water present in both dates is treated as persistent water, while new post-period water is mapped as probable inundation.',
        'model_info': {'before': pre_info, 'after': post_info, 'model_backed': model_backed},
        'map_bounds_wgs84': meta.get('bounds_wgs84'),
        'legend': [
            {'label': 'Probable new inundation', 'color': '#ef4444'},
            {'label': 'Persistent water', 'color': '#2563eb'},
            {'label': 'Receded water', 'color': '#f59e0b'},
        ],
    }


def vegetation_change(first_path: str | Path, second_path: str | Path, out_path: str | Path) -> Dict[str, Any]:
    a0 = read_raster(first_path)
    b0 = read_raster(second_path)
    a, b, meta, warnings = _align_second_to_first(first_path, second_path)

    def veg_index(raw, rgb):
        data = raw['data']
        if data.shape[0] >= 4:
            red = data[2].astype(np.float32)
            nir = data[3].astype(np.float32)
            return (nir-red)/(nir+red+1e-6), 'NDVI(b4,b3)'
        arr = rgb.astype(np.float32)/255.0
        rr,g,bl = arr[:,:,0],arr[:,:,1],arr[:,:,2]
        return 2*g-rr-bl, 'ExcessGreen'

    ia, ma = veg_index(a0, a)
    ib, mb = veg_index(b0, b)
    if ia.shape != ib.shape:
        ib = cv2.resize(ib, (ia.shape[1], ia.shape[0]), interpolation=cv2.INTER_LINEAR)
    loss = ia - ib
    th = max(0.12, float(np.percentile(loss, 80)))
    mask = _clean_mask((loss > th).astype(np.uint8)*255)
    overlay = _overlay(b, mask, color=(245, 158, 11), alpha=0.6)
    Image.fromarray(overlay).save(out_path)
    geojson, area_m2 = _area(mask, meta)
    pct = float((mask > 0).mean()*100)
    confidence = min(0.88, 0.58 + (0.12 if ma.startswith('NDVI') and mb.startswith('NDVI') else 0) + (0.07 if meta.get('crs') else 0))
    return {
        'overlay_path': str(out_path), 'geojson': geojson,
        'statistics': {'vegetation_loss_percent': round(pct,2), 'loss_area_km2': round(area_m2/1e6,4) if area_m2 else None},
        'confidence': round(confidence,3), 'confidence_type': 'operational_heuristic',
        'warnings': warnings + ([] if ma.startswith('NDVI') else ['RGB fallback vegetation index used because NIR band was unavailable.']),
        'method': f'{ma}->{mb}_difference', 'map_bounds_wgs84': meta.get('bounds_wgs84')
    }


def summarize_image(path: str | Path, out_path: str | Path) -> Dict[str, Any]:
    r = read_raster(path)
    rgb = r['rgb']
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    arr = rgb.astype(np.float32)
    green_score = np.maximum(0, arr[:,:,1] - (arr[:,:,0]+arr[:,:,2])/2)
    water_score = np.maximum(0, arr[:,:,2] - (arr[:,:,0]+arr[:,:,1])/2)
    stats = {
        'mean_brightness': round(float(gray.mean()), 1),
        'green_dominant_percent': round(float((green_score > 12).mean()*100), 2),
        'blue_dominant_percent': round(float((water_score > 12).mean()*100), 2),
    }
    Image.fromarray(rgb).save(out_path)
    return {
        'overlay_path': str(out_path), 'geojson': {'type':'FeatureCollection','features':[]},
        'statistics': stats, 'confidence': 0.58, 'confidence_type': 'operational_heuristic',
        'warnings': ['VLM offline — semantic image summary is a local visual baseline. Connect a remote-sensing VLM for richer VQA.'],
        'method': 'image_statistics', 'map_bounds_wgs84': r['meta'].get('bounds_wgs84')
    }


def external_change_detection(first_path: str | Path, second_path: str | Path, mask_png: bytes, out_path: str | Path, method: str, confidence: float = 0.88) -> Dict[str, Any]:
    """Convert an externally generated binary change mask into SatQuery outputs."""
    a, b, meta, warnings = _align_second_to_first(first_path, second_path)
    import io
    mask_img = Image.open(io.BytesIO(mask_png)).convert('L')
    mask = np.array(mask_img)
    if mask.shape[:2] != b.shape[:2]:
        mask = cv2.resize(mask, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_NEAREST)
    # Handle palette/probability images robustly.
    threshold = 127 if mask.max() > 1 else 0
    mask = _clean_mask((mask > threshold).astype(np.uint8) * 255, iterations=1)
    overlay = _overlay(b, mask, color=(255, 72, 80), alpha=0.62)
    Image.fromarray(overlay).save(out_path)
    geojson, area_m2 = _area(mask, meta)
    pct = float((mask > 0).mean() * 100)
    return {
        'overlay_path': str(out_path),
        'geojson': geojson,
        'statistics': {
            'change_percent': round(pct, 2),
            'changed_area_km2': round(area_m2 / 1e6, 4) if area_m2 else None,
        },
        'confidence': max(0.0, min(float(confidence), 0.99)),
        'confidence_type': 'specialist_model_output',
        'warnings': warnings,
        'method': method,
        'model_info': {'model_backed': True, 'model': method},
        'map_bounds_wgs84': meta.get('bounds_wgs84'),
    }


def _feature_collection_area_m2(geojson: Dict[str, Any]) -> float:
    """Best-effort area for GeoJSON returned by a segmentation service."""
    total = 0.0
    crs_value = None
    crs_obj = geojson.get('crs') if isinstance(geojson, dict) else None
    if isinstance(crs_obj, str):
        crs_value = crs_obj
    elif isinstance(crs_obj, dict):
        crs_value = (crs_obj.get('properties') or {}).get('name') or crs_obj.get('name')
    features = geojson.get('features', []) if isinstance(geojson, dict) else []
    if not features:
        return 0.0
    try:
        if crs_value:
            src_crs = CRS.from_user_input(crs_value.replace('urn:ogc:def:crs:EPSG::', 'EPSG:'))
            if src_crs.is_projected:
                return float(sum(max(shape(f['geometry']).area, 0.0) for f in features if f.get('geometry')))
            transformer = Transformer.from_crs(src_crs, CRS.from_epsg(6933), always_xy=True)
            return float(sum(max(shp_transform(transformer.transform, shape(f['geometry'])).area, 0.0) for f in features if f.get('geometry')))
        # GeoJSON normally uses WGS84 when CRS is absent.
        transformer = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(6933), always_xy=True)
        return float(sum(max(shp_transform(transformer.transform, shape(f['geometry'])).area, 0.0) for f in features if f.get('geometry')))
    except Exception:
        return 0.0


def grounded_segmentation_result(path: str | Path, out_path: str | Path, geojson: Dict[str, Any], prompt: str, method: str) -> Dict[str, Any]:
    """Normalize text-prompt segmentation output into SatQuery result schema."""
    r = read_raster(path)
    Image.fromarray(r['rgb']).save(out_path)
    count = len(geojson.get('features', [])) if isinstance(geojson, dict) else 0
    area_m2 = _feature_collection_area_m2(geojson)
    return {
        'overlay_path': str(out_path),
        'geojson': geojson if isinstance(geojson, dict) else {'type': 'FeatureCollection', 'features': []},
        'statistics': {
            'detected_object_count': count,
            'detected_area_km2': round(area_m2 / 1e6, 4) if area_m2 > 0 else None,
            'target': prompt,
        },
        'confidence': 0.84 if count > 0 else 0.55,
        'confidence_type': 'specialist_model_output',
        'warnings': [] if count > 0 else [f'No reliable {prompt} regions were returned by the text-segmentation specialist.'],
        'method': method,
        'model_info': {'model_backed': True, 'model': method, 'prompt': prompt},
        'map_bounds_wgs84': r['meta'].get('bounds_wgs84'),
        'answer': f"Detected {count} mapped {prompt} region{'s' if count != 1 else ''}." if count else f"No reliable {prompt} regions were detected.",
    }


def visual_answer_result(path: str | Path, out_path: str | Path, answer: str, method: str, temporal: bool = False,
                         second_path: str | Path | None = None, model_info=None, latency_ms=None, model_confidence=None) -> Dict[str, Any]:
    """Wrap a remote-sensing VLM answer while preserving map/source metadata.

    ``model_info`` is the VLM service response (answer/model_name/model_version/
    backend/latency_ms/model_confidence/...). model_confidence stays ``None``
    unless the service supplies a genuinely calibrated value.
    """
    r = read_raster(path)
    Image.fromarray(r['rgb']).save(out_path)
    info = model_info if isinstance(model_info, dict) else {}
    meta = r['meta']
    display = str(info.get('model_name') or info.get('model') or method)
    stats = {
        'vision_assistant': True,
        'temporal_images_used': 2 if temporal and second_path else 1,
    }
    return {
        'overlay_path': str(out_path),
        'geojson': {'type': 'FeatureCollection', 'features': []},
        'statistics': stats,
        'confidence': 0.78,
        'confidence_type': 'vision_language_model',
        'warnings': ['Vision-language answers are semantic interpretations. Quantitative area or change claims should come from specialist geospatial tools.'] + list(info.get('warnings') or []),
        'method': method,
        'model_info': {
            'model_backed': True,
            'model': display,
            'model_name': info.get('model_name'),
            'model_version': info.get('model_version'),
            'backend': info.get('backend'),
            'fallback_used': False,
            'fallback_reason': None,
            'latency_ms': latency_ms if latency_ms is not None else info.get('latency_ms'),
            'model_confidence': model_confidence if model_confidence is not None else info.get('model_confidence'),
            'input_source': meta.get('source') or meta.get('platform'),
            'sensor': meta.get('platform') or meta.get('sensor'),
            'modality': meta.get('modality'),
            'acquisition_date': meta.get('acquired_at') or meta.get('period_label'),
            'resolution': meta.get('resolution'),
            'processing_timestamp': datetime.now(timezone.utc).isoformat(),
        },
        'map_bounds_wgs84': r['meta'].get('bounds_wgs84'),
        'answer': answer.strip(),
    }
