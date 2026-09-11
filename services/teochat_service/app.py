"""SatQuery EO-VLM inference service.

Runs a real remote-sensing vision-language model behind an isolated HTTP
service so the main GIS backend never shares dependency pins.

Endpoints
---------
* ``GET  /health``   -> model state; ``status=ready`` ONLY when the checkpoint is
   loaded AND a real smoke inference succeeded.
* ``POST /smoke``    -> run one real inference on a bundled satellite-style patch
   and upgrade /health to ``ready``.
* ``POST /vqa``      -> single/multi image visual QA (multipart or JSON).
* ``POST /vqa-temporal`` -> two-image change-oriented visual QA (multipart or JSON).

Each /vqa-family response carries full provenance and ``model_backed``/``fallback_used``
truth so SatQuery can display the exact model that answered.

Soft-declined images (blank / tiny / mostly-NoData / corrupt / SAR) return
HTTP 200 with ``"answer": null`` and a ``declined_block`` reason so the caller
falls back honestly instead of fabricating a scene description.
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import model as M
from preprocessing import prep_satellite_image, render_smoke_patch, to_png_bytes

app = FastAPI(title="SatQuery EO-VLM Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SMOKE_PATCH = None  # rendered once


class VQAJSON(BaseModel):
    query: str
    image_paths: List[str]


class VQATemporalJSON(BaseModel):
    query: str
    earlier_path: str
    later_path: str


def _read_upload(file: UploadFile) -> bytes:
    """Read an UploadFile body with either sync or async backing."""
    raw = file.file.read() if hasattr(file.file, "read") else None
    if raw is not None:
        return raw
    import anyio
    return anyio.from_thread.run(file.read)


_PREPROCESSING_KEYS = (
    "width",
    "height",
    "dtype_name",
    "source_format",
    "bands_used",
    "band_descriptions",
    "nodata_ratio",
    "stretch_method",
    "scale",
)


def _payload(ok: bool, **fields) -> Dict[str, Any]:
    return {"answer": None, "model_backed": False, "fallback_used": True, "declined_block": None, **fields} if not ok else fields


def _write_temp_png(rgb) -> str:
    fd, path = tempfile.mkstemp(prefix="satquery_vlm_", suffix=".png")
    os.close(fd)
    with open(path, "wb") as fh:
        fh.write(to_png_bytes(rgb))
    return path


def _prepare(raw: bytes, name: str) -> Dict[str, Any]:
    res = prep_satellite_image(raw, name)
    if not res.get("ok"):
        code = res.get("code", "unsupported")
        # SAR is a routing matter, but the service double-guards.
        return {
            "answer": None,
            "model_backed": False,
            "fallback_used": True,
            "declined_block": {"code": code, "reason": res.get("reason", "Unsupported image input.")},
        }
    res["png_path"] = _write_temp_png(res["rgb"])
    pre = {k: res.get(k) for k in _PREPROCESSING_KEYS}
    pre["modality"] = res.get("modality")
    return {"ok": True, "pre": pre, "png_path": res["png_path"]}


def _temporal_question(question: str, backend_name: str, n_images: int) -> str:
    if backend_name == "cpu-vlm" and n_images >= 2:
        return (
            "The first image is the EARLIER scene and the second image is the LATER scene. "
            "Was there a change between them? Describe what changed. Question: " + question.strip()
        )
    return question.strip()


def _run(entries: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    for entry in entries:
        if not entry.get("ok"):
            block = entry.get("declined_block") or {"code": "rejected", "reason": "Image rejected before inference."}
            return {
                "answer": None,
                "model_backed": False,
                "fallback_used": True,
                "declined_block": block,
                "latency_ms": None,
                "model_confidence": None,
            }
    t0 = time.time()
    try:
        meta = M.run_inference([e["png_path"] for e in entries], _temporal_question(question, M.health()["backend"], len(entries)))
    except Exception as exc:
        raise HTTPException(500, f"VLM inference failed: {exc}")
    for e in entries:
        os.path.exists(e["png_path"]) and os.remove(e["png_path"])
    return {
        "answer": meta["answer"],
        "model_name": meta["model_name"],
        "model_version": meta["model_version"] or None,
        "model_backed": True,
        "fallback_used": False,
        "latency_ms": meta["latency_ms"],
        "model_confidence": None,
        "images_used": len(entries),
        "backend": meta["backend"],
        "device": meta["device"],
        "dtype": meta["dtype"],
        "preprocessing": [e.get("pre") for e in entries],
        "warnings": [],
    }


@app.get("/")
def info():
    return {
        "service": M.backend_display_name(M.get_engine()) if _model_present() else "SatQuery EO-VLM Service",
        "endpoints": ["/health", "/smoke", "/vqa", "/vqa-temporal"],
    }


def _model_present() -> bool:
    return M._ENGINE["backend"] is not None


@app.get("/health")
def health():
    return M.health()


@app.post("/smoke")
def smoke():
    global SMOKE_PATCH
    if SMOKE_PATCH is None:
        SMOKE_PATCH = _write_temp_png(render_smoke_patch())
    try:
        meta = M.run_inference([SMOKE_PATCH], "Describe all material land features in this satellite image.")
    except Exception as exc:
        raise HTTPException(500, f"Smoke inference failed: {exc}")
    M.mark_smoke_ok()
    return {
        "smoke_ok": True,
        "answer": meta["answer"],
        "model_name": meta["model_name"],
        "model_version": meta["model_version"] or None,
        "latency_ms": meta["latency_ms"],
        "model_backed": True,
        "fallback_used": False,
    }


@app.post("/vqa")
def vqa_multi(image: UploadFile = File(...), image_2: Optional[UploadFile] = File(None), question: str = Form(...)):
    entries = [_prepare(_read_upload(image), image.filename or "image.tif")]
    if image_2 is not None:
        entries.append(_prepare(_read_upload(image_2), image_2.filename or "image2.tif"))
    return _run(entries, question)


@app.post("/vqa-temporal")
def vqa_temporal_multi(earlier: UploadFile = File(...), later: UploadFile = File(...), question: str = Form(...)):
    entries = [
        _prepare(_read_upload(earlier), earlier.filename or "earlier.tif"),
        _prepare(_read_upload(later), later.filename or "later.tif"),
    ]
    return _run(entries, question)


@app.post("/vqa")
def vqa_json(inp: VQAJSON):
    if not inp.query.strip() or not inp.image_paths:
        raise HTTPException(400, "query and at least one image path are required")
    entries = []
    for p in inp.image_paths:
        if not os.path.exists(p):
            raise HTTPException(400, f"Image path not visible to this service: {p}")
        with open(p, "rb") as fh:
            raw = fh.read()
        entries.append(_prepare(raw, os.path.basename(p)))
    return _run(entries, inp.query.strip())


@app.post("/vqa-temporal")
def vqa_temporal_json(inp: VQATemporalJSON):
    paths = [inp.earlier_path, inp.later_path]
    entries = []
    for p in paths:
        if not os.path.exists(p):
            raise HTTPException(400, f"Image path not visible to this service: {p}")
        with open(p, "rb") as fh:
            raw = fh.read()
        entries.append(_prepare(raw, os.path.basename(p)))
    return _run(entries, inp.query.strip())


@app.on_event("startup")
def _startup_log():
    print(
        "======================================================================",
        flush=True,
    )
    print("SatQuery EO-VLM service starting", flush=True)
    print(f"  TEOCHAT_ENGINE   : {os.getenv('TEOCHAT_ENGINE', 'auto')}", flush=True)
    print(f"  CPU model        : {os.getenv('TEOCHAT_CPU_VLM', 'Qwen/Qwen2-VL-2B-Instruct')}", flush=True)
    print(f"  TEOChat model    : {os.getenv('TEOCHAT_MODEL', 'jirvin16/TEOChat')}", flush=True)
    print(f"  max_new_tokens   : {os.getenv('TEOCHAT_MAX_NEW_TOKENS', '192')}", flush=True)
    print("  Model loads lazily on first /vqa or /smoke request.", flush=True)
    print(
        "======================================================================",
        flush=True,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8021")))