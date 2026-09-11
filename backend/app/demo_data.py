from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np
import rasterio
from rasterio.transform import from_origin

DEMO_SPECS: List[Tuple[str, str, str]] = [
    ('Indore_2023_optical.tif', 'optical', 'optical_before'),
    ('Indore_2026_optical.tif', 'optical', 'optical_after'),
    ('Assam_July_2025_S1_SAR_demo.tif', 'sar', 'sar_before'),
    ('Assam_August_2025_S1_SAR_demo.tif', 'sar', 'sar_after'),
    ('Assam_August_2025_S2_optical_demo.tif', 'optical', 'optical_assam'),
]


def _write_optical_demo(path: Path, seed: int, origin=(75.72, 22.80), changed=False):
    rng = np.random.default_rng(seed)
    h, w = 360, 520
    base = np.zeros((3, h, w), dtype=np.uint8)
    base[0] = rng.normal(68, 12, (h, w)).clip(0, 255)
    base[1] = rng.normal(96, 18, (h, w)).clip(0, 255)
    base[2] = rng.normal(62, 10, (h, w)).clip(0, 255)
    yy, xx = np.ogrid[:h, :w]
    river = np.abs(yy - (210 + 25 * np.sin(xx / 55))) < 17
    base[:, river] = np.array([35, 55, 78])[:, None]
    if changed:
        for x, y, ww, hh in [(320, 70, 65, 42), (405, 125, 52, 58), (260, 110, 44, 52)]:
            base[:, y:y + hh, x:x + ww] = np.array([150, 145, 138])[:, None, None]
    transform = from_origin(origin[0], origin[1], 0.00022, 0.00022)
    with rasterio.open(path, 'w', driver='GTiff', height=h, width=w, count=3, dtype='uint8', crs='EPSG:4326', transform=transform) as dst:
        dst.write(base)
        dst.update_tags(source='synthetic_demo', location_name='Indore, Madhya Pradesh, India')


def _write_assam_optical_demo(path: Path, seed: int, acquired_at: str):
    """Geo-correct, synthetic Sentinel-2-like optical demo for the same
    upper-Assam AOI (Dhemaji) as the SAR demo, so optical + SAR fusion runs
    against genuinely overlapping scenes."""
    rng = np.random.default_rng(seed)
    h, w = 420, 600
    base = np.zeros((3, h, w), dtype=np.uint8)
    base[0] = rng.normal(62, 10, (h, w)).clip(0, 255)
    base[1] = rng.normal(92, 14, (h, w)).clip(0, 255)
    base[2] = rng.normal(48, 9, (h, w)).clip(0, 255)
    yy, xx = np.ogrid[:h, :w]
    river = np.abs(yy - (235 + 28 * np.sin(xx / 70))) < 18
    base[:, river] = np.array([34, 58, 92])[:, None]
    flood = (((xx - 360) / 160) ** 2 + ((yy - 255) / 86) ** 2) < 1
    flood &= ~river
    base[:, flood] = np.array([38, 62, 96])[:, None]
    f2 = (((xx - 170) / 88) ** 2 + ((yy - 175) / 48) ** 2) < 1
    f2 &= ~river
    base[:, f2] = np.array([36, 60, 94])[:, None]
    for cx, cy, rw, rh in [(90, 60, 30, 22), (140, 120, 26, 20), (330, 70, 34, 26), (470, 180, 30, 24)]:
        field = (((xx - cx) / rw) ** 2 + ((yy - cy) / rh) ** 2) < 1
        base[:, field] = np.array([128, 138, 84])[:, None]
    transform = from_origin(94.42, 27.88, 0.001, 0.001)
    with rasterio.open(path, 'w', driver='GTiff', height=h, width=w, count=3, dtype='uint8', crs='EPSG:4326', transform=transform) as dst:
        dst.write(base)
        dst.update_tags(
            source='synthetic_demo',
            acquired_at=acquired_at,
            location_name='Upper Assam demo AOI (Dhemaji region), Assam, India',
            modality='optical',
        )


def _write_assam_sar_demo(path: Path, seed: int, flood_stage: str, acquired_at: str):
    """Geo-correct, synthetic dual-pol SAR demo around Dhemaji/upper Assam."""
    rng = np.random.default_rng(seed)
    h, w = 420, 600
    vv = rng.normal(-10.5, 2.2, (h, w)).astype(np.float32)
    vh = rng.normal(-17.0, 2.4, (h, w)).astype(np.float32)
    yy, xx = np.ogrid[:h, :w]
    river = np.abs(yy - (235 + 28 * np.sin(xx / 70))) < 18
    vv[river] = rng.normal(-21.5, 1.0, int(river.sum()))
    vh[river] = rng.normal(-28.0, 1.2, int(river.sum()))
    if flood_stage == 'after':
        flood = (((xx - 360) / 160) ** 2 + ((yy - 255) / 86) ** 2) < 1
        flood &= ~river
        vv[flood] = rng.normal(-20.5, 1.2, int(flood.sum()))
        vh[flood] = rng.normal(-27.0, 1.3, int(flood.sum()))
        f2 = (((xx - 170) / 88) ** 2 + ((yy - 175) / 48) ** 2) < 1
        f2 &= ~river
        vv[f2] = rng.normal(-19.8, 1.1, int(f2.sum()))
        vh[f2] = rng.normal(-26.3, 1.3, int(f2.sum()))
    transform = from_origin(94.42, 27.88, 0.001, 0.001)
    with rasterio.open(path, 'w', driver='GTiff', height=h, width=w, count=2, dtype='float32', crs='EPSG:4326', transform=transform, compress='deflate') as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, 'VV_dB')
        dst.set_band_description(2, 'VH_dB')
        dst.update_tags(
            source='synthetic_demo',
            acquired_at=acquired_at,
            location_name='Upper Assam demo AOI (Dhemaji region), Assam, India',
            modality='sar',
        )


def bake_all(dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname, _mod, kind in DEMO_SPECS:
        path = dest_dir / fname
        if kind == 'optical_before':
            _write_optical_demo(path, seed=3, changed=False)
        elif kind == 'optical_after':
            _write_optical_demo(path, seed=3, changed=True)
        elif kind == 'optical_assam':
            _write_assam_optical_demo(path, seed=23, acquired_at='2025-08-19')
        elif kind == 'sar_before':
            _write_assam_sar_demo(path, seed=17, flood_stage='before', acquired_at='2025-07-18')
        else:
            _write_assam_sar_demo(path, seed=17, flood_stage='after', acquired_at='2025-08-19')


def period_label_for(kind: str):
    if kind == 'sar_before':
        return 'July 2025'
    if kind in ('sar_after', 'optical_assam'):
        return 'August 2025'
    return None