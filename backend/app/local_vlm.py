from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from .geo_tools import make_preview

MODEL_DIR = os.getenv("CLIP_MODEL_DIR", "/app/models/clip")

DEFAULT_LABELS = [
    "urban area with buildings and roads",
    "agricultural farmland and crop fields",
    "forest and dense vegetation",
    "water bodies, rivers and lakes",
    "bare soil, sand or dry terrain",
    "mountainous or hilly terrain",
]

_WATER_LABELS = [
    "flooded fields and submerged land",
    "standing water after heavy rain",
    "normal dry farmland",
    "rivers, lakes and ponds",
    "clouds and cloud shadows",
]

_VEG_LABELS = [
    "dense green vegetation and forest",
    "moderate vegetation and cropland",
    "sparse vegetation and dry grass",
    "bare soil and urban surface",
    "water bodies",
]

_BUILD_LABELS = [
    "buildings and houses",
    "roads and highways",
    "water bodies and rivers",
    "farmland fields",
    "forest and trees",
    "bare ground",
]


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


class LocalCLIPAdapter:
    """Real free keyless vision AI that runs INSIDE the container.

    Uses OpenAI CLIP ViT-B/32 (baked into the image) for zero-shot scene /
    water / vegetation / building classification with real model.confidences.
    Returns ``None`` (existing deterministic chain) whenever the model is
    missing or CPU inference fails.
    """

    def __init__(self):
        self.model_dir = MODEL_DIR
        self._model = None
        self._lock = threading.Lock()
        self._load_error: Optional[str] = None
        self._attempts = 0
        self._log = logging.getLogger('local_clip')

    @property
    def model_available(self) -> bool:
        root = Path(self.model_dir)
        if not root.exists() or (root / ".missing").exists():
            return False
        return (root / "config.json").exists()

    @property
    def enabled(self) -> bool:
        return self.model_available

    def _load(self):
        if self._model is None and self._attempts < 3:
            with self._lock:
                if self._model is None and self._attempts < 3:
                    self._attempts += 1
                    try:
                        import torch
                        from transformers import CLIPModel, CLIPProcessor
                        torch.set_num_threads(min(4, os.cpu_count() or 4))
                        self._model = CLIPModel.from_pretrained(
                            self.model_dir, local_files_only=True, torch_dtype=torch.float32
                        )
                        self._model.eval()
                        self._processor = CLIPProcessor.from_pretrained(self.model_dir, local_files_only=True)
                        self._load_error = None
                        self._log.info('CLIP loaded from %s (cpu)', self.model_dir)
                    except Exception as exc:
                        self._load_error = str(exc)
                        self._model = None
                        self._processor = None
                        self._log.warning('CLIP load attempt %s failed: %s', self._attempts, exc)

    def health(self) -> Dict[str, Any]:
        if not self.model_available:
            return {"enabled": False, "reachable": False, "note": "CLIP model not baked. Deterministic fallback active.", "model_name": "clip-vit-base-patch32 (local)"}
        return {
            "enabled": True,
            "available": True,
            "reachable": True,
            "ready": self._model is not None,
            "loading_lazy": True,
            "note": "Local CLIP loads on first analysis (no API key needed).",
            "model_name": "clip-vit-base-patch32 (local)",
            "provider": "Local CLIP zero-shot (free, no API key)",
        }

    def _labels_for(self, query: str) -> List[str]:
        low = query.lower()
        if any(k in low for k in ("flood", "water", "submerge", "inundat", "damage", "sar")):
            return _WATER_LABELS
        if any(k in low for k in ("veget", "forest", "ndvi", "green", "crop")):
            return _VEG_LABELS
        if any(k in low for k in ("building", "object", "highlight", "segment", "detect", "ground", "urban", "settlement")):
            return _BUILD_LABELS
        return DEFAULT_LABELS

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        self._load()
        if self._model is None:
            return None
        img = _to_pil(image_paths[0])
        if img is None:
            return None
        labels = self._labels_for(query)
        t0 = time.time()
        try:
            inputs = self._processor(text=labels, images=img, return_tensors="pt", padding=True)
            import torch
            with torch.no_grad():
                outputs = self._model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).squeeze(0)
            top = torch.topk(probs, k=min(3, len(labels)))
            scored = [(labels[i], float(probs[i])) for i in top.indices.tolist()]
        except Exception as exc:
            self._load_error = str(exc)
            self._log.warning('CLIP inference failed: %s', exc)
            return None
        latency_ms = int((time.time() - t0) * 1000)
        best = scored[0]
        listing = '; '.join(f'{lab} {pct:.1f}%' for lab, pct in scored)
        answer = (
            f"Image analysis (free on-device AI): the scene best matches "
            f"'{best[0]}' with {best[1] * 100:.1f}% confidence. "
            f"Top classes: {listing}. "
            f"Note: this keyless model classifies scene content; "
            f"numeric area/change statistics come from the raster engine."
        )
        return {
            "answer": answer,
            "model": "CLIP ViT-B/32 (local free AI)",
            "model_name": "CLIP ViT-B/32 (local free AI)",
            "model_version": "clip-vit-base-patch32",
            "model_backed": True,
            "model_confidence": round(best[1], 3),
            "confidence": round(best[1], 3),
            "fallback_used": False,
            "latency_ms": latency_ms,
            "images_used": 1,
            "backend": "local_clip_zero_shot_free",
            "provider": "Local CLIP zero-shot (no API key)",
            "warnings": [
                "Analysis used the on-container CLIP model (free, offline). "
                "Connect GEMINI_API_KEY for richer language answers."
            ],
        }