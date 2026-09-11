"""Local HTTP bridge for the official TEOChat repository.

Run this file *inside the TEOChat conda environment* after installing the official
repo. SatQuery communicates over HTTP so dependency pins do not collide with the
main GIS backend.

Environment variables:
  TEOCHAT_MODEL=jirvin16/TEOChat
  TEOCHAT_DEVICE=cuda
  TEOCHAT_LOAD_8BIT=1
  PORT=8021
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="SatQuery TEOChat Bridge")


class VQAIn(BaseModel):
    query: str
    image_paths: List[str]


@lru_cache(maxsize=1)
def _load():
    try:
        from videollava.eval.eval import load_model
        from videollava.eval.inference import run_inference_single
    except Exception as exc:
        raise RuntimeError(
            "TEOChat is not importable. Clone/install https://github.com/ermongroup/TEOChat in this environment."
        ) from exc
    model_path = os.getenv("TEOCHAT_MODEL", "jirvin16/TEOChat")
    device = os.getenv("TEOCHAT_DEVICE", "cuda")
    load_8bit = os.getenv("TEOCHAT_LOAD_8BIT", "1").lower() in {"1", "true", "yes"}
    tokenizer, model, processor = load_model(
        model_path=model_path,
        model_base=None,
        load_8bit=load_8bit,
        device=device,
    )
    return tokenizer, model, processor, run_inference_single, model_path


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": os.getenv("TEOCHAT_MODEL", "jirvin16/TEOChat"),
        "loaded": _load.cache_info().currsize > 0,
    }


@app.post("/vqa")
def vqa(inp: VQAIn):
    if not inp.query.strip() or not inp.image_paths:
        raise HTTPException(400, "query and at least one image path are required")
    missing = [p for p in inp.image_paths if not os.path.exists(p)]
    if missing:
        raise HTTPException(400, f"Image paths are not visible to the bridge: {missing}")
    try:
        tokenizer, model, processor, run_inference_single, model_path = _load()
        prefix = (
            "These are satellite/earth-observation images in chronological order: <video> "
            if len(inp.image_paths) > 1
            else "This is a satellite/earth-observation image: <video> "
        )
        answer = run_inference_single(model, processor, tokenizer, prefix + inp.query.strip(), inp.image_paths)
        return {"answer": str(answer).strip(), "model": f"TEOChat ({model_path})", "images_used": len(inp.image_paths)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8021")))
