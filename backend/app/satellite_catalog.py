from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def _intersection_score(item_bbox: Sequence[float], target: Sequence[float]) -> float:
    il, ib, ir, it = item_bbox
    tl, tb, tr, tt = target
    ix = max(0.0, min(ir, tr) - max(il, tl))
    iy = max(0.0, min(it, tt) - max(ib, tb))
    inter = ix * iy
    target_area = max((tr - tl) * (tt - tb), 1e-9)
    return inter / target_area


def _item_date(item: Any) -> str:
    dt = item.datetime or item.properties.get("datetime") or item.properties.get("start_datetime")
    if hasattr(dt, "date"):
        return dt.date().isoformat()
    return str(dt or "")[:10]


def _search_s1(bbox: Sequence[float], start: str, end: str, max_items: int = 60) -> List[Any]:
    try:
        from pystac_client import Client
        import planetary_computer
    except ImportError as exc:
        raise RuntimeError("Automatic Sentinel retrieval needs pystac-client and planetary-computer. Reinstall backend requirements.txt.") from exc

    catalog = Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)
    search = catalog.search(
        collections=["sentinel-1-rtc"],
        bbox=list(bbox),
        datetime=f"{start}/{end}",
        query={"sar:instrument_mode": {"eq": "IW"}},
        max_items=max_items,
    )
    items = list(search.items())
    # Keep dual-pol scenes because the model expects VV+VH.
    items = [i for i in items if "vv" in i.assets and "vh" in i.assets]
    items.sort(key=lambda i: (_intersection_score(i.bbox, bbox), _item_date(i)), reverse=True)
    return items


def _select_pair(first: List[Any], second: List[Any], bbox: Sequence[float]) -> Tuple[Any, Any]:
    if not first or not second:
        raise RuntimeError("No dual-polarisation Sentinel-1 RTC scenes were found for one of the requested periods.")
    best = None
    best_score = -1e9
    for a in first[:20]:
        for b in second[:20]:
            orbit_a = a.properties.get("sat:relative_orbit")
            orbit_b = b.properties.get("sat:relative_orbit")
            orbit_bonus = 2.0 if orbit_a is not None and orbit_a == orbit_b else 0.0
            platform_bonus = 0.25 if a.properties.get("platform") == b.properties.get("platform") else 0.0
            score = _intersection_score(a.bbox, bbox) + _intersection_score(b.bbox, bbox) + orbit_bonus + platform_bonus
            if score > best_score:
                best_score = score
                best = (a, b)
    assert best is not None
    return best


def _safe_window(src: rasterio.DatasetReader, bbox_wgs84: Sequence[float]) -> Window:
    if not src.crs:
        raise RuntimeError("Remote SAR asset has no CRS.")
    left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84, densify_pts=21)
    win = from_bounds(left, bottom, right, top, transform=src.transform)
    full = Window(0, 0, src.width, src.height)
    try:
        win = win.intersection(full)
    except Exception as exc:
        raise RuntimeError("Requested AOI does not intersect the selected Sentinel-1 scene.") from exc
    if win.width < 2 or win.height < 2:
        raise RuntimeError("Requested AOI intersection is too small.")
    return win


def _read_remote_band(href: str, bbox_wgs84: Sequence[float], max_side: int = 1024) -> Tuple[np.ndarray, Any, Any]:
    env_opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
        "GDAL_HTTP_MULTIRANGE": "YES",
    }
    with rasterio.Env(**env_opts):
        with rasterio.open(href) as src:
            win = _safe_window(src, bbox_wgs84)
            scale = max(float(win.width) / max_side, float(win.height) / max_side, 1.0)
            out_w = max(32, int(round(win.width / scale)))
            out_h = max(32, int(round(win.height / scale)))
            arr = src.read(1, window=win, out_shape=(out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
            base_transform = src.window_transform(win)
            transform = base_transform * Affine.scale(float(win.width) / out_w, float(win.height) / out_h)
            return arr, transform, src.crs


def _write_dualpol(item: Any, bbox_wgs84: Sequence[float], out_path: Path, label: str) -> Dict[str, Any]:
    vv, transform, crs = _read_remote_band(item.assets["vv"].href, bbox_wgs84)
    vh, transform2, crs2 = _read_remote_band(item.assets["vh"].href, bbox_wgs84)
    if vv.shape != vh.shape:
        raise RuntimeError("VV and VH assets resolved to different raster shapes.")
    if crs != crs2:
        raise RuntimeError("VV and VH assets resolved to different CRS values.")

    # Planetary Computer S1 RTC is commonly linear backscatter. Convert to dB when
    # values are non-negative; keep already-dB assets unchanged.
    def to_db(x: np.ndarray) -> np.ndarray:
        finite = x[np.isfinite(x)]
        if finite.size and float(np.nanpercentile(finite, 5)) >= 0:
            return (10.0 * np.log10(np.clip(x, 1e-8, None))).astype(np.float32)
        return x.astype(np.float32)

    vv_db, vh_db = to_db(vv), to_db(vh)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=vv.shape[0],
        width=vv.shape[1],
        count=2,
        dtype="float32",
        crs=crs,
        transform=transform,
        compress="deflate",
    ) as dst:
        dst.write(vv_db, 1)
        dst.write(vh_db, 2)
        dst.set_band_description(1, "VV_dB")
        dst.set_band_description(2, "VH_dB")
        dst.update_tags(
            source="Microsoft Planetary Computer Sentinel-1 RTC",
            stac_item=item.id,
            acquired_at=_item_date(item),
            modality="sar",
            label=label,
        )
    return {
        "stac_id": item.id,
        "acquired_at": _item_date(item),
        "platform": item.properties.get("platform", "Sentinel-1"),
        "relative_orbit": item.properties.get("sat:relative_orbit"),
        "orbit_state": item.properties.get("sat:orbit_state"),
        "source": "planetary_computer_sentinel_1_rtc",
    }


def retrieve_sentinel1_pair(query_context: Dict[str, Any], output_dir: Path, prefix: str) -> List[Dict[str, Any]]:
    location = query_context.get("location") or {}
    date_range = query_context.get("date_range") or {}
    periods = date_range.get("periods") or []
    if len(periods) < 2:
        raise RuntimeError("Temporal flood retrieval needs two time periods, for example July and August 2025.")
    bbox = location.get("analysis_bbox") or location.get("bbox")
    if not bbox:
        raise RuntimeError("No geospatial AOI could be resolved from the query.")

    p1, p2 = periods[0], periods[-1]
    first = _search_s1(bbox, p1["start"], p1["end"])
    second = _search_s1(bbox, p2["start"], p2["end"])
    a, b = _select_pair(first, second, bbox)

    out1 = output_dir / f"{prefix}_before.tif"
    out2 = output_dir / f"{prefix}_after.tif"
    m1 = _write_dualpol(a, bbox, out1, p1["label"])
    m2 = _write_dualpol(b, bbox, out2, p2["label"])
    return [
        {"path": out1, "filename": f"{location.get('key','AOI')}_{p1['label'].replace(' ','_')}_Sentinel1_RTC.tif", "modality": "sar", "extra_meta": {**m1, "period_label": p1["label"], "location_name": location.get("name"), "requested_bbox_wgs84": bbox}},
        {"path": out2, "filename": f"{location.get('key','AOI')}_{p2['label'].replace(' ','_')}_Sentinel1_RTC.tif", "modality": "sar", "extra_meta": {**m2, "period_label": p2["label"], "location_name": location.get("name"), "requested_bbox_wgs84": bbox}},
    ]


def resolve_location_online(place_text: str) -> Optional[Dict[str, Any]]:
    """Resolve an unknown place name with OpenStreetMap Nominatim.

    This is an optional network enhancement. It is deliberately called only when
    the deterministic offline gazetteer did not resolve the place.
    """
    if not place_text:
        return None
    try:
        import requests
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place_text, "format": "jsonv2", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "SatQueryAI/3.0 (research prototype)"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        item = rows[0]
        # Nominatim boundingbox order: south, north, west, east.
        south, north, west, east = [float(x) for x in item["boundingbox"]]
        bbox = [west, south, east, north]
        # Avoid huge state/country extents in live inference: crop around center.
        width = max(east - west, 0.02)
        height = max(north - south, 0.02)
        cx, cy = (west + east) / 2, (south + north) / 2
        half_w = min(max(width * 0.35, 0.08), 0.35)
        half_h = min(max(height * 0.35, 0.08), 0.28)
        analysis_bbox = [cx - half_w, cy - half_h, cx + half_w, cy + half_h]
        return {
            "key": re.sub(r"[^a-z0-9]+", "_", place_text.lower()).strip("_") or "aoi",
            "name": item.get("display_name") or place_text,
            "bbox": bbox,
            "analysis_bbox": analysis_bbox,
            "source": "nominatim",
            "coverage_note": "The place was resolved online; live analysis uses a bounded AOI around the resolved center for responsive inference.",
        }
    except Exception:
        return None
