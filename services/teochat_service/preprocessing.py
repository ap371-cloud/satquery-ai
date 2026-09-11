"""Raster/image -> model-ready RGB preprocessing for the TEOChat inference service.

Handles PNG, JPEG, TIFF and GeoTIFF inputs across uint8 / uint16 / float32 and
1 / 3 / 4+ band stacks. Band-aware RGB selection is used when metadata or band
descriptions identify the actual red / green / blue bands. SAR imagery is
refused before it can reach a semantics model that assumes optical meaning.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from PIL import Image

try:
    import rasterio
    from rasterio.io import MemoryFile
    _RASTERIO = True
except Exception:  # pragma: no cover
    _RASTERIO = False


def _stretch(arr: np.ndarray, lo_pct: float = 2.0, hi_pct: float = 98.0) -> np.ndarray:
    """Percentile linear stretch of a single band to uint8, ignoring nodata/nan."""
    arr = arr.astype(np.float32)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [lo_pct, hi_pct])
    if not np.isfinite(lo) or not np.isfinite(hi):
        return np.zeros(arr.shape, dtype=np.uint8)
    if hi <= lo:
        hi = lo + 1.0
    out = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    return (out * 255.0).astype(np.uint8)


def _detect_sar(descriptions: List[str], count: int, tags: Dict[str, Any]) -> bool:
    low = [str(d or "").lower() for d in descriptions]
    tag_mod = str(tags.get("modality") or "").lower()
    if tag_mod in {"sar", "radar"}:
        return True
    joined = " ".join(low)
    if "vv" in joined and "vh" in joined:
        return True
    if count <= 2 and any("v" in k for k in low) and "sar" in tags.get("source", "").lower():
        return True
    return False


def _band_order(src) -> List[int]:
    """Resolve (red, green, blue) band indices from metadata when possible."""
    count = src.count
    descs = [str(d or "").lower() for d in (src.descriptions or [])]
    r = next((i for i, d in enumerate(descs) if "red" in d and "nir" not in d and "edge" not in d), None)
    g = next((i for i, d in enumerate(descs) if "green" in d), None)
    b = next((i for i, d in enumerate(descs) if "blue" in d), None)
    if r is not None and g is not None and b is not None:
        return [r, g, b]
    if count >= 4:
        # Sentinel-2 style: B2, B3, B4, B8 ...
        return [2, 1, 0]
    if count >= 3:
        return [0, 1, 2]
    return [0, 0, 0]


def _read_tiff(raw: bytes) -> Dict[str, Any]:
    if not _RASTERIO:
        return {"ok": False, "reason": "Raster support unavailable on this service host (rasterio not installed)."}
    data = None
    with MemoryFile(raw) as mem:
        with mem.open() as src:
            count = src.count
            descs = list(src.descriptions or [])
            tags = src.tags()
            dtype_name = str(src.dtypes[0]) if src.dtypes else "uint8"
            nodata = src.nodata
            if _detect_sar(descs, count, tags):
                return {"ok": False, "code": "sar", "reason": "SAR imagery is not routed to an optical-semantics vision model."}
            arr = src.read()
            h, w = src.height, src.width
    bands = []
    nodata_ratio = 0.0
    valid_per_band = []
    for band_idx in range(count):
        band = arr[band_idx].astype(np.float32)
        nodata_mask = np.zeros(band.shape, dtype=bool)
        if nodata is not None and np.isfinite(nodata).any():
            nodata_mask |= np.isclose(band, float(nodata))
        nodata_mask |= ~np.isfinite(band)
        ratio = float(nodata_mask.mean()) if band.size else 1.0
        valid_per_band.append(ratio)
        finite = band[np.isfinite(band)]
        fill = float(np.nanmedian(finite)) if finite.size else 0.0
        band = np.where(nodata_mask, fill, band)
        bands.append(band)
        nodata_ratio = max(nodata_ratio, ratio)

    order = _band_order_count(count)
    red, green, blue = (bands[order[0]], bands[order[1]], bands[order[2]])
    rgb = np.stack([red, green, blue], axis=-1)
    raw_gray = rgb.mean(axis=-1)
    raw_std = float(np.std(raw_gray[np.isfinite(raw_gray)])) if np.isfinite(raw_gray).any() else 0.0
    if dtype_name != "uint8":
        rgb = np.stack([_stretch(red), _stretch(green), _stretch(blue)], axis=-1)
    else:
        rgb = np.clip(rgb, 0, 255)
    return {
        "ok": True,
        "rgb": rgb,
        "width": int(w),
        "height": int(h),
        "dtype_name": dtype_name,
        "source_format": "tiff",
        "bands_used": order,
        "band_descriptions": descs,
        "nodata_ratio": round(nodata_ratio, 4),
        "raw_std": round(raw_std, 4),
        "stretch_method": "none" if dtype_name == "uint8" else "percentile_2_98",
        "modality": "sar" if False else "optical",
    }


def _band_order_count(count: int) -> List[int]:
    if count >= 4:
        return [2, 1, 0]
    if count == 3:
        return [0, 1, 2]
    if count == 2:
        return [0, 0, 1]
    return [0, 0, 0]


def _read_plain_image(raw: bytes, name: str) -> Dict[str, Any]:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        return {"ok": False, "reason": f"Could not decode image: {exc}"}
    if img.mode != "RGB":
        img = img.convert("RGB")
    rgb = np.array(img)
    return {
        "ok": True,
        "rgb": rgb,
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "dtype_name": str(rgb.dtype),
        "source_format": "pixel",
        "bands_used": [0, 1, 2],
        "band_descriptions": [],
        "nodata_ratio": 0.0,
        "stretch_method": "none",
        "modality": "optical",
    }


def prep_satellite_image(raw: bytes, name: str, max_side: int = 512) -> Dict[str, Any]:
    """Return a model-ready RGB PIL image for any supported satellite input.

    Failure dictionaries carry a machine-readable ``code`` so the caller can map
    the result to a truthful fallback (blank / tiny / mostly-nodata / corrupt /
    SAR / unsupported).
    """
    name_l = (name or "").lower()
    if not raw:
        return {"ok": False, "code": "empty", "reason": "Empty image payload."}

    if name_l.endswith((".tif", ".tiff")):
        result = _read_tiff(raw)
    elif name_l.endswith((".png", ".jpg", ".jpeg", ".jpe")):
        result = _read_plain_image(raw, name)
    else:
        # Decide by magic bytes.
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            result = _read_plain_image(raw, "image.png")
        elif raw[:3] == b"\xff\xd8\xff":
            result = _read_plain_image(raw, "image.jpg")
        else:
            result = _read_tiff(raw)
        if not result.get("ok"):
            result = _read_plain_image(raw, "image.png")

    if not result.get("ok"):
        if result.get("code") == "sar":
            return result
        result["code"] = result.get("code") or "unsupported"
        return result

    rgb = result["rgb"]
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        return {"ok": False, "code": "unsupported", "reason": "Raster did not resolve to a 3-channel RGB visualization."}

    raw_std = result.get("raw_std")
    if raw_std is None:
        raw_std = float(np.std(rgb))
    if rgb.shape[0] < 16 or rgb.shape[1] < 16:
        return {"ok": False, "code": "tiny", "reason": "Image is too small for reliable semantic interpretation.", "width": result["width"], "height": result["height"]}
    if raw_std < 2.0:
        return {"ok": False, "code": "blank", "reason": "Image is essentially blank or uniform (insufficient visual evidence).", "width": result["width"], "height": result["height"]}
    if result.get("nodata_ratio", 0.0) > 0.6:
        return {"ok": False, "code": "nodata", "reason": "Image is mostly NoData; no meaningful surface content to interpret.", "nodata_ratio": result["nodata_ratio"]}

    h, w = rgb.shape[:2]
    scale = max(h, w) / float(max_side)
    if scale > 1.0:
        nh, nw = max(int(round(h / scale)), 16), max(int(round(w / scale)), 16)
        if cv2 is not None:
            rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        else:
            rgb = np.array(Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS))
    result["scale"] = scale if scale > 1.0 else 1.0
    result["rgb"] = rgb
    return result


def to_png_bytes(pil_rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(pil_rgb).save(buf, format="PNG")
    return buf.getvalue()


def render_smoke_patch(seed: int = 7, size: int = 384) -> np.ndarray:
    """Deterministic synthetic satellite-style patch used only for model warm-up."""
    rng = np.random.default_rng(seed)
    h, w = size, size
    base = np.zeros((h, w, 3), dtype=np.uint8)
    base[..., 0] = rng.normal(68, 12, (h, w)).clip(0, 255)
    base[..., 1] = rng.normal(96, 16, (h, w)).clip(0, 255)
    base[..., 2] = rng.normal(60, 10, (h, w)).clip(0, 255)
    yy, xx = np.ogrid[:h, :w]
    river = np.abs(yy - (200 + 28 * np.sin(xx / 58))) < 15
    base[river] = np.array([38, 58, 80], dtype=np.uint8)
    urban = (np.abs(xx - 70) < 52) & (np.abs(yy - 80) < 44)
    base[urban] = np.array([150, 145, 138], dtype=np.uint8)
    veg = (np.abs(xx - 240) < 90) & (np.abs(yy - 280) < 60)
    base[veg] = np.array([70, 128, 66], dtype=np.uint8)
    return base.astype(np.uint8)