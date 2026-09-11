from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from .geo_tools import make_preview

MODEL_DIR = os.getenv("FLORENCE_MODEL_DIR", "/app/models/florence2")


def _to_pil(path: str) -> Optional[Image.Image]:
    p = Path(path)
    try:
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            return Image.open(p).convert("RGB")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            make_preview(p, tmp.name)
            tmp_path = tmp.name
        img = Image.open(tmp_path).convert("RGB")
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return img
    except Exception:
        return None


def _format_od(result: Any) -> str:
    """Turn Florence <OD> output into a readable bullet list of detections."""
    try:
        od = result
        if isinstance(result, dict):
            od = result.get("<OD>") or result.get("od") or result
        lines = []
        for entry in od:
            if isinstance(entry, (list, tuple)) and len(entry) == 3:
                bbox = entry[0]
                label = str(entry[1])
                conf = float(entry[2]) if entry[2] is not None else 1.0
                lines.append(f"- {label} (confidence {conf:.2f}) at box {[round(x) for x in bbox]}")
            elif isinstance(entry, (list, tuple)) and entry:
                lines.append(f"- {entry}")
        return "\n".join(lines) if lines else str(od)
    except Exception:
        return str(result)


class LocalFlorenceAdapter:
    """Real free vision-language AI that runs INSIDE the container — no API key.

    Uses Microsoft Florence-2-base baked into the image at build time. Falls back
    to ``ask=None`` (existing deterministic chain) whenever the model is missing,
    not downloaded, or CPU inference fails.
    """

    def __init__(self):
        self.model_dir = MODEL_DIR
        self._model = None
        self._lock = threading.Lock()
        self._load_error: Optional[str] = None

    @property
    def model_available(self) -> bool:
        root = Path(self.model_dir)
        if not root.exists() or (root / ".missing").exists():
            return False
        return (root / "config.json").exists()

    @property
    def enabled(self) -> bool:
        return self.model_available

    def _model_id(self) -> str:
        return os.getenv("FLORENCE_MODEL_ID", "microsoft/Florence-2-base")

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None and self._load_error is None:
                    try:
                        import torch
                        from transformers import AutoProcessor, Florence2ForConditionalGeneration
                        torch.set_num_threads(min(4, os.cpu_count() or 4))
                        self._model = Florence2ForConditionalGeneration.from_pretrained(
                            self.model_dir, local_files_only=True, torch_dtype=torch.float32
                        )
                        self._model.eval()
                        self._processor = AutoProcessor.from_pretrained(self.model_dir, local_files_only=True)
                        return
                    except Exception as exc:
                        self._load_error = str(exc)
                        self._model = None
                        self._processor = None
                        return
        # already loaded or failed

    def health(self) -> Dict[str, Any]:
        if not self.model_available:
            return {"enabled": False, "reachable": False, "note": "Florence-2 model not baked. Deterministic fallback active.", "model_name": "florence-2 (local)"}
        return {
            "enabled": True,
            "available": True,
            "reachable": True,
            "ready": self._model is not None,
            "loading_lazy": True,
            "note": "Local Florence-2 loads on first analysis (no API key needed).",
            "model_name": "florence-2-base (local)",
            "provider": "Local Florence-2 (no API key)",
        }

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        self._load()
        if self._model is None:
            return None
        img = _to_pil(image_paths[0])
        if img is None:
            return None
        low = query.lower()
        if any(k in low for k in ("building", "object", "highlight", "segment", "detect", "ground")):
            task = "<OD>"
        else:
            task = "<MORE_DETAILED_CAPTION>"
        t0 = time.time()
        try:
            inputs = self._processor(text=task, images=img, return_tensors="pt")
            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=256,
                num_beams=3,
                do_sample=False,
            )
            generated = self._processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            answer = self._processor.post_process_generation(generated, task=task, image_size=img.size)
        except Exception as exc:
            self._load_error = str(exc)
            return None
        latency_ms = int((time.time() - t0) * 1000)
        text = _format_od(answer) if task == "<OD>" else (str(answer) if not isinstance(answer, dict) else str(answer))
        model_name = os.getenv("FLORENCE_MODEL_NAME", "Florence-2-base (local free AI)")
        return {
            "answer": text,
            "model": model_name,
            "model_name": model_name,
            "model_version": "florence-2-base",
            "model_backed": True,
            "model_confidence": 0.7,
            "fallback_used": False,
            "latency_ms": latency_ms,
            "images_used": 1,
            "backend": "local_florence2_free",
            "provider": "Local Florence-2 (no API key)",
            "warnings": ["Analysis used the on-container Florence-2 model (CPU). Connect GEMINI_API_KEY for a stronger cloud model."],
        }