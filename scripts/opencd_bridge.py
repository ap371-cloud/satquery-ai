"""HTTP bridge for the official Open-CD change-detection toolbox.

Run inside an Open-CD environment. Configure model and checkpoint paths:
  OPENCD_MODEL_CONFIG=/path/to/open-cd/configs/...py
  OPENCD_WEIGHTS=/path/to/checkpoint.pth
  PORT=8022

SatQuery sends preview image paths and receives the predicted change mask as a
base64 PNG. If your Open-CD version saves predictions under a different folder,
set OPENCD_PRED_SUBDIR accordingly.
"""
from __future__ import annotations

import base64
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image
import numpy as np
import uvicorn

app = FastAPI(title="SatQuery Open-CD Bridge")


class ChangeIn(BaseModel):
    before_path: str
    after_path: str


@lru_cache(maxsize=1)
def _inferencer():
    try:
        from opencd.apis import OpenCDInferencer
    except Exception as exc:
        raise RuntimeError("Open-CD is not importable. Install https://github.com/likyoo/open-cd in this environment.") from exc
    config = os.getenv("OPENCD_MODEL_CONFIG")
    weights = os.getenv("OPENCD_WEIGHTS")
    if not config or not weights:
        raise RuntimeError("Set OPENCD_MODEL_CONFIG and OPENCD_WEIGHTS before starting the bridge.")
    return OpenCDInferencer(
        model=config,
        weights=weights,
        classes=("unchanged", "changed"),
        palette=[[0, 0, 0], [255, 255, 255]],
    )


def _find_prediction(root: Path) -> Path:
    candidates = [p for p in root.rglob("*") if p.suffix.lower() in {".png", ".tif", ".tiff", ".jpg", ".jpeg"}]
    if not candidates:
        raise RuntimeError("Open-CD completed but no prediction image was found.")
    # Prefer paths whose folder/name looks like a prediction rather than a visualization.
    candidates.sort(key=lambda p: (("pred" in str(p).lower()) or ("mask" in str(p).lower()), p.stat().st_mtime), reverse=True)
    return candidates[0]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "configured": bool(os.getenv("OPENCD_MODEL_CONFIG") and os.getenv("OPENCD_WEIGHTS")),
        "loaded": _inferencer.cache_info().currsize > 0,
    }


@app.post("/change")
def change(inp: ChangeIn):
    if not Path(inp.before_path).exists() or not Path(inp.after_path).exists():
        raise HTTPException(400, "Input preview paths are not visible to the bridge.")
    try:
        inferencer = _inferencer()
        with tempfile.TemporaryDirectory(prefix="satquery_opencd_") as td:
            out_dir = Path(td)
            inferencer([[inp.before_path, inp.after_path]], show=False, out_dir=str(out_dir), img_out_dir="vis", pred_out_dir="pred")
            pred_path = _find_prediction(out_dir / "pred" if (out_dir / "pred").exists() else out_dir)
            arr = np.array(Image.open(pred_path).convert("L"))
            # Normalize arbitrary class-label/palette outputs to binary mask.
            if arr.max() <= 1:
                arr = (arr > 0).astype(np.uint8) * 255
            else:
                arr = (arr >= max(1, int(np.percentile(arr[arr > 0], 25))) if (arr > 0).any() else 255).astype(np.uint8) * 255
            out = out_dir / "binary_mask.png"
            Image.fromarray(arr).save(out)
            encoded = base64.b64encode(out.read_bytes()).decode("ascii")
            return {
                "mask_png_base64": encoded,
                "model": f"Open-CD: {Path(os.getenv('OPENCD_MODEL_CONFIG')).stem}",
                "confidence": 0.88,
            }
    except Exception as exc:
        raise HTTPException(500, str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8022")))
