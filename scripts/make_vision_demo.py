"""Generate deterministic demo scenes for the model-backed Vision Assistant.

Writes GeoTIFFs (and PNG previews) into demo_data/vision/:

* vision_sample.tif  — golden scene: river valley + fields + village (uint16)
* vd_01..vd_05.tif   — five materially different land-cover scenes for the
                       five-image semantic test
* vd_06_fourband.tif — four-band Sentinel-2-style stack (B2 B3 B4 B8) to verify
                       band-aware RGB resolution on the model service
* sb_*.tif/.png      — deliberately degenerate inputs for honest negative tests
                       (blank, all-black-ish, mostly-NoData, SAR, tiny)

All scenes are tagged ``source=synthetic_demo`` so SatQuery never mistakes them
for real observations. Call as a module or simulate pixels locally.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_origin

import sys
from pathlib import Path

VISION_DIR = Path(__file__).resolve().parents[1] / "demo_data" / "vision"


def _river_mask(h, w, amp=26, period=58, cy=205, width=16):
    yy, xx = np.ogrid[:h, :w]
    return np.abs(yy - (cy + amp * np.sin(xx / period))) < width


def _ellipse(h, w, cx, cy, rx, ry):
    yy, xx = np.ogrid[:h, :w]
    return (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1


def _rect(h, w, x, y, rw, rh):
    yy, xx = np.ogrid[:h, :w]
    return (xx >= x) & (xx < x + rw) & (yy >= y) & (yy < y + rh)


def _field_grid(h, w, x0, y0, cols, rows, cell, rng):
    mask = np.zeros((h, w), dtype=bool)
    phase = rng.integers(0, 4)
    for i in range(cols):
        for j in range(rows):
            if (i + j + phase) % 3 == 0:
                mask |= _rect(h, w, x0 + i * cell, y0 + j * cell, cell - 3, cell - 3)
    return mask


def _texture(h, w, rng, mean, spread):
    return rng.normal(mean, spread, (h, w))


def _scene_rgb(h, w, seed, kind):
    rng = np.random.default_rng(seed)
    yy, xx = np.ogrid[:h, :w]

    if kind == "river_agri":
        r = _texture(h, w, rng, 96, 14) + 30 * np.sin(yy / 90)
        g = _texture(h, w, rng, 138, 16)
        b = _texture(h, w, rng, 92, 12)
        river = _river_mask(h, w, cy=210)
        r[river], g[river], b[river] = 52, 74, 96
        fields = _field_grid(h, w, x0=18, y0=28, cols=7, rows=8, cell=58, rng=rng)
        tone = rng.integers(120, 170)
        g[fields] = tone + rng.normal(0, 12, g[fields].shape)
        r[fields] = tone * 0.72
        b[fields] = tone * 0.55
        village = _ellipse(h, w, 405, 96, 34, 24)
        r[village] = 168
        g[village] = 160
        b[village] = 150
    elif kind == "dense_urban":
        r = _texture(h, w, rng, 158, 10)
        g = _texture(h, w, rng, 152, 9)
        b = _texture(h, w, rng, 146, 9)
        for bx, by in [(30, 34), (112, 30), (196, 36), (288, 32), (66, 128), (150, 122), (236, 128), (322, 124),
                       (40, 220), (122, 216), (206, 222), (294, 218)]:
            mask = _rect(h, w, bx, by, 46, 42)
            r[mask] = 176 + rng.normal(0, 5, mask.sum())
            g[mask] = 170 + rng.normal(0, 5, mask.sum())
            b[mask] = 164 + rng.normal(0, 5, mask.sum())
        redroof = _ellipse(h, w, 170, 270, 26, 22)
        r[redroof], g[redroof], b[redroof] = 188, 108, 96
        main_road_h = _rect(h, w, 172, 0, 10, h)
        main_road_v = _rect(h, w, 0, 95, w, 9)
        r[main_road_h], g[main_road_h], b[main_road_h] = 128, 126, 124
        r[main_road_v], g[main_road_v], b[main_road_v] = 130, 128, 126
    elif kind == "forest":
        yy2 = _ellipse(h, w, 120, 90, 300, 150)
        r = _texture(h, w, rng, 60, 8)
        g = _texture(h, w, rng, 118, 14)
        b = _texture(h, w, rng, 66, 8)
        r[yy2], g[yy2], b[yy2] = 66, 146, 74
        for i in range(60):
            cx, cy = int(rng.integers(20, w - 20)), int(rng.integers(20, h - 20))
            rr = int(rng.integers(38, 92))
            clump = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) < rr
            r[clump] = np.clip(r[clump] + rng.normal(4, 6), 0, 255)
            g[clump] = np.clip(g[clump] + rng.normal(8, 7), 0, 255)
        clearing = _ellipse(h, w, 300, 62, 52, 34)
        r[clearing], g[clearing], b[clearing] = 118, 152, 112
    elif kind == "coastal":
        r = _texture(h, w, rng, 140, 12)
        g = _texture(h, w, rng, 138, 11)
        b = _texture(h, w, rng, 128, 10)
        water = (xx / (w - 1)) < (0.62 + 0.05 * np.sin(yy / 40))
        r[water], g[water], b[water] = 52, 78, 116
        waves = rng.uniform(0, 1, (h, w)) > 0.96
        r[waves & water] = 74
        g[waves & water] = 96
        b[waves & water] = 132
        spit = _ellipse(h, w, 330, 232, 118, 30)
        r[spit], g[spit], b[spit] = 214, 204, 174
    elif kind == "mixed_urban_water":
        r = _texture(h, w, rng, 128, 12)
        g = _texture(h, w, rng, 132, 12)
        b = _texture(h, w, rng, 122, 11)
        lake = _ellipse(h, w, 150, 120, 108, 72)
        r[lake], g[lake], b[lake] = 56, 84, 122
        park = _ellipse(h, w, 96, 108, 40, 26)
        r[park], g[park], b[park] = 82, 148, 92
        for bx, by in [(300, 46), (352, 122), (240, 190), (330, 210)]:
            m = _rect(h, w, bx, by, 52, 36)
            r[m] = 176
            g[m] = 168
            b[m] = 160
            rd = _rect(h, w, bx + 4, by + 6, 8, 22)
            r[rd] = 186
            g[rd] = 104
            b[rd] = 98
    else:
        raise ValueError(kind)

    rgb = np.dstack([np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)])
    return rgb.astype(np.uint8)


SCENES = {
    "vision_sample.tif": ("river_agri", 11, "River valley with agricultural fields and a village along a winding river"),
    "vd_01_river_agriculture.tif": ("river_agri", 3, "Green agricultural checkboard fields beside a broad river"),
    "vd_02_dense_urban.tif": ("dense_urban", 5, "Dense rectilinear city block grid with arterial roads"),
    "vd_03_forest.tif": ("forest", 7, "Extensive dense forest canopy"),
    "vd_04_coastal_water.tif": ("coastal", 13, "Coastline with open water and a sand spit"),
    "vd_05_mixed_urban_water.tif": ("mixed_urban_water", 8, "City blocks beside an urban lake with a park"),
}


def _write_tif(path: Path, rgb_uint8: np.ndarray, tags: dict, crs="EPSG:4326", origin=(75.72, 22.80), res=0.00012,
               dtype="uint8", extra_bands: dict | None = None, descs: list | None = None):
    h, w = rgb_uint8.shape[:2]
    if extra_bands:
        count = rgb_uint8.shape[2] + len(extra_bands)
    else:
        count = rgb_uint8.shape[2]
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=count, dtype=dtype, crs=crs,
                       transform=from_origin(origin[0], origin[1], res, res), compress="deflate") as dst:
        for i in range(rgb_uint8.shape[2]):
            dst.write(rgb_uint8[..., i].astype(rgb_uint8.dtype if rgb_uint8.dtype != np.uint16 else np.uint16), i + 1)
            if descs and i < len(descs):
                dst.set_band_description(i + 1, descs[i])
        if extra_bands:
            for key, band in extra_bands.items():
                dst.write(band, rgb_uint8.shape[2] + 1)
                if descs and len(descs) >= rgb_uint8.shape[2] + 1:
                    dst.set_band_description(rgb_uint8.shape[2] + 1, descs[rgb_uint8.shape[2]])
        dst.update_tags(**tags)


def generate_all():
    VISION_DIR.mkdir(parents=True, exist_ok=True)

    scenes_out = []
    for fname, (kind, seed, _) in SCENES.items():
        rgb = _scene_rgb(560, 700, seed, kind)
        uint16 = (rgb.astype(np.float32) * 12.0).astype(np.uint16)
        tags = {
            "source": "synthetic_demo",
            "location_name": f"Synthetic demo scene — {SCENES[fname][2]}",
            "modality": "optical",
            "platform": "Synthetic (demo)",
            "resolution": "12 m",
            "acquired_at": "2026-06-15",
            "period_label": "June 2026",
        }
        _write_tif(VISION_DIR / fname, uint16, tags, dtype="uint16")
        Image.fromarray(rgb).save(VISION_DIR / fname.replace(".tif", ".png"))
        scenes_out.append(VISION_DIR / fname)

    # Four-band Sentinel-2 style band stack: B2 B3 B4 B8 (uint16)
    rgb = _scene_rgb(560, 700, 4, "river_agri")
    uint16 = (rgb.astype(np.float32) * 12.0).astype(np.uint16)
    nir = np.clip(uint16[..., 1].astype(np.float32) * 1.35 + 180, 0, 65535).astype(np.uint16)
    tags4 = {
        "source": "synthetic_demo",
        "location_name": "Synthetic four-band demo (Sentinel-2 band ordering)",
        "modality": "optical",
        "platform": "Sentinel-2 (synthetic)",
        "resolution": "10 m",
        "acquired_at": "2026-06-15",
    }
    _write_tif(VISION_DIR / "vd_06_fourband.tif", uint16, tags4, dtype="uint16",
               extra_bands={"nir": nir}, descs=["Blue", "Green", "Red", "NIR"])
    Image.fromarray(rgb).save(VISION_DIR / "vd_06_fourband.png")

    # ---- Negative test inputs ------------------------------------------ #
    # blank / uniform
    blank = np.full((200, 260, 3), 120, dtype=np.uint8)
    _write_tif(VISION_DIR / "sb_01_blank.tif", blank, {"source": "synthetic_demo", "modality": "optical", "period_label": "test"})
    # all-black-ish (std < 2)
    black = np.full((200, 260, 3), 3, dtype=np.uint8)
    black[:, :100, :] = 4
    _write_tif(VISION_DIR / "sb_02_black.tif", black, {"source": "synthetic_demo", "modality": "optical", "period_label": "test"})
    # tiny
    tiny = (np.arange(36, dtype=np.uint8).reshape(6, 6) * 40)[..., None].repeat(3, axis=2)
    _write_tif(VISION_DIR / "sb_03_tiny.tif", tiny, {"source": "synthetic_demo", "modality": "optical", "period_label": "test"})
    # SAR (VV + VH 2 band, already handled at SatQuery router, provable here too)
    rng = np.random.default_rng(2)
    vv = rng.normal(-10.0, 2.0, (200, 260)).astype(np.float32)
    vh = rng.normal(-17.0, 2.2, (200, 260)).astype(np.float32)
    yy = np.arange(200)[:, None]
    water = np.abs(yy - 90) < 20
    water = np.broadcast_to(water, (200, 260))
    vv[water] = -22.0
    vh[water] = -29.0
    with rasterio.open(VISION_DIR / "sb_04_sar.tif", "w", driver="GTiff", height=200, width=260, count=2,
                       dtype="float32", crs="EPSG:4326",
                       transform=from_origin(94.4, 27.8, 0.001, 0.001), compress="deflate") as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, "VV_dB")
        dst.set_band_description(2, "VH_dB")
        dst.update_tags(source="synthetic_demo", modality="sar", platform="Sentinel-1 (synthetic)", period_label="test")

    return scenes_out


if __name__ == "__main__":
    out = generate_all()
    print(f"Generated {len(out)} semantic scenes + negatives in {VISION_DIR}")
    for p in out:
        print(f"  {p.name}")