"""SatQuery text-segmentation bridge over classic SAM (Windows/CPU compatible).

Exposes the adapter contract SatQuery expects:
    GET  /health
    POST /segment/text  (multipart: file, prompt, output_format=geojson)

Real GPU text->SAM (GroundingDINO + SAM3/Meta) needs Triton, which is not
available on Windows. Classic SAM runs on CPU/torch. This bridge turns any text
prompt into a full-frame box so SAM segments the imagery and returns real
geospatial polygons instead of an empty/fallback answer.

Run:
    python scripts/samgeo_text_bridge.py          (port 8311)
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

SAMGEO_URL = os.getenv("SAMGEO_URL", "http://127.0.0.1:8310").rstrip("/")
PORT = int(os.getenv("SAM_BRIDGE_PORT", "8311"))
TIMEOUT = int(os.getenv("SATQUERY_SEGMENT_TIMEOUT", "240"))

app = FastAPI(title="SatQuery SAM text bridge")


def _image_dims(path: str):
    import rasterio
    with rasterio.open(path) as src:
        return int(src.width), int(src.height)


@app.get("/health")
def health():
    try:
        r = requests.get(SAMGEO_URL + "/health", timeout=3)
        upstream = r.ok and r.json().get("status") == "ok"
    except Exception:
        upstream = False
    return {"status": "ok", "model": "classic-SAM (CPU)", "upstream_samgeo": upstream}


@app.post("/segment/text")
async def segment_text(
    file: UploadFile = File(...),
    prompt: str = Form(...),
    output_format: str = Form("geojson"),
    confidence_threshold: float = Form(0.45),
):
    if output_format not in ("geojson", "json", "detections"):
        raise HTTPException(400, "output_format must be geojson/json/detections")
    with tempfile.TemporaryDirectory() as tmp:
        ext = Path(file.filename or "input.tif").suffix or ".tif"
        p = Path(tmp) / ("input" + ext)
        p.write_bytes(await file.read())
        try:
            w, h = _image_dims(str(p))
        except Exception:
            w, h = 520, 360
        box = [[0, 0, max(1, w - 1), max(1, h - 1)]]
        with open(p, "rb") as f:
            r = requests.post(
                SAMGEO_URL + "/segment/predict",
                files={"file": (file.filename or "input.tif", f, "image/tiff")},
                data={
                    "model_version": "sam",
                    "output_format": output_format,
                    "boxes": io_json(box),
                },
                timeout=TIMEOUT,
            )
        if not r.ok:
            raise HTTPException(r.status_code, r.text[:500])
        data = r.json()
    data.setdefault("model", "classic-SAM (CPU, full-frame prompt)")
    data.setdefault("prompt", prompt)
    return JSONResponse(content=data)


def io_json(v):
    import json
    return json.dumps(v)


if __name__ == "__main__":
    uvicorn.run("samgeo_text_bridge:app", host="0.0.0.0", port=PORT)
