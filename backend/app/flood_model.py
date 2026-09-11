from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = BASE / "models" / "best_model.pt"


def model_status() -> Dict[str, Any]:
    checkpoint = Path(os.getenv("SATQUERY_FLOOD_MODEL_PATH", str(DEFAULT_CHECKPOINT)))
    try:
        import torch  # noqa: F401
        import segmentation_models_pytorch  # noqa: F401
        deps = True
    except Exception:
        deps = False
    return {
        "checkpoint_path": str(checkpoint),
        "checkpoint_present": checkpoint.exists(),
        "dependencies_present": deps,
        "ready": checkpoint.exists() and deps,
        "architecture": "U-Net / EfficientNet-B0 / VV+VH" if checkpoint.exists() and deps else None,
    }


def _lee_like_filter(channel: np.ndarray, k: int = 7) -> np.ndarray:
    # Lightweight local-statistics speckle suppression suitable for inference.
    x = channel.astype(np.float32)
    mean = cv2.boxFilter(x, -1, (k, k), normalize=True)
    mean_sq = cv2.boxFilter(x * x, -1, (k, k), normalize=True)
    var = np.maximum(mean_sq - mean * mean, 0.0)
    noise_var = float(np.nanmedian(var))
    weight = var / (var + noise_var + 1e-6)
    return mean + weight * (x - mean)


def preprocess_sar(arr: np.ndarray) -> np.ndarray:
    if arr.ndim != 3 or arr.shape[0] < 2:
        raise ValueError("Model-backed SAR inference requires two bands: VV and VH.")
    x = arr[:2].astype(np.float32)
    out = []
    for band in x:
        finite = band[np.isfinite(band)]
        if finite.size and float(np.nanpercentile(finite, 5)) >= 0:
            band = 10.0 * np.log10(np.clip(band, 1e-8, None))
        band = np.nan_to_num(band, nan=0.0, posinf=10.0, neginf=-30.0)
        band = _lee_like_filter(band, 7)
        band = np.clip(band, -30.0, 10.0)
        band = (band + 30.0) / 40.0
        out.append(band.astype(np.float32))
    return np.stack(out, axis=0)


@lru_cache(maxsize=1)
def _load_model():
    status = model_status()
    if not status["ready"]:
        return None, None
    import torch
    import segmentation_models_pytorch as smp

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = smp.Unet(
        encoder_name="efficientnet-b0",
        encoder_weights=None,
        in_channels=2,
        classes=1,
        activation=None,
    )
    checkpoint = torch.load(status["checkpoint_path"], map_location=device)
    state = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state)
    model = model.to(device).eval()
    return model, device


def _predict_tiled(model, device, arr: np.ndarray, tile_size: int = 128, stride: int = 64) -> np.ndarray:
    import torch
    c, h, w = arr.shape
    if h < tile_size or w < tile_size:
        pad_h = max(0, tile_size - h)
        pad_w = max(0, tile_size - w)
        arr = np.pad(arr, ((0, 0), (0, pad_h), (0, pad_w)), mode="constant")
    _, hp, wp = arr.shape
    rows = list(range(0, max(1, hp - tile_size + 1), stride))
    cols = list(range(0, max(1, wp - tile_size + 1), stride))
    if not rows or rows[-1] != hp - tile_size:
        rows.append(max(0, hp - tile_size))
    if not cols or cols[-1] != wp - tile_size:
        cols.append(max(0, wp - tile_size))
    yy, xx = np.mgrid[:tile_size, :tile_size]
    sigma = tile_size / 4.0
    g = np.exp(-((xx - tile_size / 2) ** 2 + (yy - tile_size / 2) ** 2) / (2 * sigma ** 2)).astype(np.float32)
    prob = np.zeros((hp, wp), np.float32)
    weight = np.zeros((hp, wp), np.float32)
    for r in rows:
        for c0 in cols:
            tile = arr[:, r:r + tile_size, c0:c0 + tile_size]
            t = torch.from_numpy(tile).unsqueeze(0).to(device)
            with torch.no_grad():
                p = torch.sigmoid(model(t)).squeeze().detach().cpu().numpy().astype(np.float32)
            prob[r:r + tile_size, c0:c0 + tile_size] += p * g
            weight[r:r + tile_size, c0:c0 + tile_size] += g
    prob = prob / np.maximum(weight, 1e-6)
    return prob[:h, :w]


def predict_water(arr: np.ndarray) -> Optional[Dict[str, Any]]:
    model, device = _load_model()
    if model is None:
        return None
    x = preprocess_sar(arr)
    probs = _predict_tiled(model, device, x)
    mask = (probs >= 0.5).astype(np.uint8) * 255
    return {
        "mask": mask,
        "probabilities": probs,
        "mean_probability": float(probs[mask > 0].mean()) if (mask > 0).any() else 0.0,
        "model": "Sentinel Flood Mapper U-Net EfficientNet-B0",
        "model_backed": True,
    }
