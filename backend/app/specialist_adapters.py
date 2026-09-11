from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime in ('image/tiff', 'image/tif', 'image/png', 'image/jpeg'):
        return mime
    return 'image/tiff'


class _HttpService:
    def __init__(self, env_name: str):
        self.url = os.getenv(env_name, "").rstrip("/")
        self.env_name = env_name

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "reachable": False, "env": self.env_name}
        try:
            r = requests.get(self.url + "/health", timeout=2.5)
            return {
                "enabled": True,
                "reachable": bool(r.ok),
                "detail": r.json() if r.ok else r.text[:500],
                "url": self.url,
            }
        except Exception as exc:
            return {"enabled": True, "reachable": False, "error": str(exc), "url": self.url}


class TEOChatAdapter(_HttpService):
    """Single/temporal Earth-observation VLM service.

    The service (services/teochat_service) runs a REAL remote-sensing VLM
    (either the TEOChat checkpoint on GPU or a CPU-run vision model) and does
    its own GeoTIFF preprocessing, so the ORIGINAL raster bytes are streamed as
    multipart. The response always self-identifies the actual model that ran.

    ``ask`` returns None (offline / model failure) or, for soft refusals
    (blank / SAR / mostly-NoData), a dict with ``answer=None`` plus ``reason``.
    """

    def __init__(self):
        super().__init__("TEOCHAT_URL")

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        timeout = int(os.getenv("SATQUERY_TEOCHAT_TIMEOUT", "600"))
        handles = []
        try:
            if len(image_paths) == 1:
                handles.append(open(image_paths[0], "rb"))
                files = [("image", (Path(image_paths[0]).name, handles[0], _guess_mime(image_paths[0])))]
                url = self.url + "/vqa"
            else:
                for p in image_paths[:2]:
                    handles.append(open(p, "rb"))
                files = [
                    ("earlier", (Path(image_paths[0]).name, handles[0], _guess_mime(image_paths[0]))),
                    ("later", (Path(image_paths[1]).name, handles[1], _guess_mime(image_paths[1]))),
                ]
                url = self.url + "/vqa-temporal"
            r = requests.post(url, files=files, data={"question": query}, timeout=timeout)
        except Exception:
            return None
        finally:
            for h in handles:
                try:
                    h.close()
                except Exception:
                    pass
        if not r.ok:
            return None
        try:
            data = r.json()
        except Exception:
            return None
        if isinstance(data, dict) and data.get("declined_block"):
            return {"answer": None, "declined": True, "reason": data["declined_block"].get("reason")}
        if not (isinstance(data, dict) and data.get("answer")):
            return None
        display = data.get("model_name") or data.get("model") or "Remote-sensing VLM"
        return {
            "answer": data["answer"],
            "model": display,
            "model_name": display,
            "model_version": data.get("model_version"),
            "model_backed": bool(data.get("model_backed", True)),
            "fallback_used": bool(data.get("fallback_used", False)),
            "latency_ms": data.get("latency_ms"),
            "model_confidence": data.get("model_confidence"),
            "images_used": data.get("images_used"),
            "backend": data.get("backend"),
            "device": data.get("device"),
            "dtype": data.get("dtype"),
            "preprocessing": data.get("preprocessing"),
            "warnings": data.get("warnings") or [],
        }

    def health(self) -> Dict[str, Any]:
        base = super().health()
        detail = base.get("detail")
        if isinstance(detail, dict):
            base["status"] = detail.get("status")
            base["model_loaded"] = bool(detail.get("model_loaded"))
            base["smoke_inference"] = bool(detail.get("smoke_inference"))
            base["ready"] = (
                detail.get("status") == "ready"
                and bool(detail.get("model_loaded"))
                and bool(detail.get("smoke_inference"))
            )
            base["backend"] = detail.get("backend")
            base["model_name"] = detail.get("model_name")
            base["model_version"] = detail.get("model_version")
            base["device"] = detail.get("device")
            base["dtype"] = detail.get("dtype")
            base["inference_count"] = detail.get("inference_count")
            base["load_ms"] = detail.get("load_ms")
            base["last_inference_ms"] = detail.get("last_inference_ms")
            base["process_memory_mb"] = detail.get("process_memory_mb")
        return base


class SARChatAdapter(_HttpService):
    """Optional SAR-specialized vision-language bridge.

    SARChat publishes SAR-domain VLM checkpoints for classification, captioning,
    VQA, counting and spatial grounding. SatQuery treats it as an isolated HTTP
    specialist using the same /vqa contract as the temporal EO VLM bridge.

    This adapter intentionally does not pretend the model is installed: set
    SARCHAT_URL only when a SARChat-compatible service is actually running.
    """

    def __init__(self):
        super().__init__("SARCHAT_URL")

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        try:
            r = requests.post(
                self.url + "/vqa",
                json={"query": query, "image_paths": image_paths},
                timeout=int(os.getenv("SATQUERY_VLM_TIMEOUT", "180")),
            )
            if r.ok:
                data = r.json()
                if isinstance(data, dict) and data.get("answer"):
                    data.setdefault("model", "SARChat")
                    return data
        except Exception:
            return None
        return None


class SamGeoAdapter(_HttpService):
    """Adapter for segment-geospatial's official REST API.

    Set SAMGEO_URL to the running API root. The package exposes /segment/text
    for text-prompt geospatial segmentation and GeoJSON output.
    """

    def __init__(self):
        super().__init__("SAMGEO_URL")

    def segment_text(self, image_path: str, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not prompt:
            return None
        try:
            with open(image_path, "rb") as f:
                r = requests.post(
                    self.url + "/segment/text",
                    files={"file": (Path(image_path).name, f, "image/tiff")},
                    data={
                        "prompt": prompt,
                        "output_format": "geojson",
                        "confidence_threshold": os.getenv("SAMGEO_CONFIDENCE", "0.45"),
                    },
                    timeout=int(os.getenv("SATQUERY_SEGMENT_TIMEOUT", "240")),
                )
            if r.ok:
                data = r.json()
                # Some API versions wrap output under a result/data field.
                if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                    return {"geojson": data, "model": "segment-geospatial/SAM text segmentation"}
                for key in ("geojson", "result", "data"):
                    if isinstance(data, dict) and isinstance(data.get(key), dict) and data[key].get("type") == "FeatureCollection":
                        return {"geojson": data[key], "model": "segment-geospatial/SAM text segmentation", "raw": data}
        except Exception:
            return None
        return None


class OpenCDAdapter(_HttpService):
    """Adapter for an Open-CD inference bridge.

    scripts/opencd_bridge.py runs in the Open-CD conda environment and returns
    the predicted binary change mask as base64 PNG.
    """

    def __init__(self):
        super().__init__("OPENCD_URL")

    def change_mask(self, before_preview: str, after_preview: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            r = requests.post(
                self.url + "/change",
                json={"before_path": before_preview, "after_path": after_preview},
                timeout=int(os.getenv("SATQUERY_CHANGE_TIMEOUT", "240")),
            )
            if not r.ok:
                return None
            data = r.json()
            encoded = data.get("mask_png_base64")
            if not encoded:
                return None
            return {
                "mask_png": base64.b64decode(encoded),
                "model": data.get("model", "Open-CD"),
                "confidence": float(data.get("confidence", 0.88)),
                "raw": data,
            }
        except Exception:
            return None


class LargeRSVQAAdapter(_HttpService):
    """Optional large-remote-sensing-image VQA bridge.

    Intended for VisionXLab/LRS-VQA or another high-resolution RSI VLM service
    exposing the same /vqa contract. SatQuery prefers it when the source raster
    is very large and the service is connected.
    """

    def __init__(self):
        super().__init__("LRSVQA_URL")

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        try:
            r = requests.post(
                self.url + "/vqa",
                json={"query": query, "image_paths": image_paths},
                timeout=int(os.getenv("SATQUERY_VLM_TIMEOUT", "180")),
            )
            if r.ok:
                data = r.json()
                if isinstance(data, dict) and data.get("answer"):
                    data.setdefault("model", "LRS-VQA")
                    return data
        except Exception:
            return None
        return None


class TerraMindAdapter(_HttpService):
    """Optional multimodal Earth-observation fusion bridge.

    TerraMind is not a chat model by itself; this adapter targets a task-specific
    TerraTorch/TerraMind service that accepts aligned optical + SAR inputs and
    returns a structured task result or semantic summary. It is intentionally
    optional because production use requires selecting/fine-tuning a downstream
    task head.
    """

    def __init__(self):
        super().__init__("TERRAMIND_URL")

    def fuse(self, query: str, optical_path: str, sar_path: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not optical_path or not sar_path:
            return None
        try:
            r = requests.post(
                self.url + "/fusion",
                json={
                    "query": query,
                    "optical_path": optical_path,
                    "sar_path": sar_path,
                },
                timeout=int(os.getenv("SATQUERY_FUSION_TIMEOUT", "300")),
            )
            if r.ok:
                data = r.json()
                if isinstance(data, dict):
                    data.setdefault("model", "TerraMind")
                    return data
        except Exception:
            return None
        return None


class SpecialistRegistry:
    def __init__(self):
        gemini = None
        try:
            from .gemini_vlm import GeminiVisionAdapter
            if os.getenv('GEMINI_API_KEY', '').strip():
                gemini = GeminiVisionAdapter()
        except Exception:
            gemini = None
        florence = None
        try:
            from .local_vlm import LocalCLIPAdapter
            fa = LocalCLIPAdapter()
            if fa.enabled:
                florence = fa
        except Exception:
            florence = None
        self.vlm = gemini if gemini else (florence if florence else TEOChatAdapter())
        self.sar_vlm = gemini if gemini else (florence if florence else SARChatAdapter())
        self.segmenter = SamGeoAdapter()
        self.change = OpenCDAdapter()
        self.large_vlm = gemini if gemini else (florence if florence else LargeRSVQAAdapter())
        self.multimodal = TerraMindAdapter()

    def health(self) -> Dict[str, Any]:
        return {
            "vision_assistant": self.vlm.health(),
            "sar_vision_assistant": self.sar_vlm.health(),
            "text_segmentation": self.segmenter.health(),
            "trained_change_detection": self.change.health(),
            "large_image_vision": self.large_vlm.health(),
            "multimodal_fusion": self.multimodal.health(),
        }
