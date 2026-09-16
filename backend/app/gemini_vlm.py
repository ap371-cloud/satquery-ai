from __future__ import annotations

import base64
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from .geo_tools import make_preview
from .security import GEMINI_SYSTEM_INSTRUCTION

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _to_jpeg_base64(path: str) -> Optional[str]:
    p = Path(path)
    try:
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            img = Image.open(p).convert("RGB")
        else:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                make_preview(p, tmp.name)
                tmp_path = tmp.name
            img = Image.open(tmp_path).convert("RGB")
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        longest = max(img.size)
        if longest > 1280:
            scale = 1280 / longest
            img = img.resize((max(1, round(img.size[0] * scale)), max(1, round(img.size[1] * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


class GeminiVisionAdapter:
    """Real online vision-language analysis via Google Gemini (free tier).

    Set GEMINI_API_KEY (AI Studio, free) to enable. Without the key this adapter
    reports ``enabled=False`` and ``ask`` returns None, so the existing
    self-hosted specialist / deterministic fallback chain keeps working.
    """

    def __init__(self):
        self.key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", "90"))

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    @property
    def display_name(self) -> str:
        return self.model

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "reachable": False, "env": "GEMINI_API_KEY", "note": "Free Gemini key provides real online vision analysis."}
        try:
            r = requests.get(f"{_BASE}/{self.model}", params={"key": self.key}, timeout=8)
            ok = bool(r.ok)
            return {
                "enabled": True,
                "reachable": ok,
                "ready": ok,
                "model_name": self.model,
                "model_loaded": None,
                "provider": "Google Gemini (free tier)",
                "url": f"{_BASE}/{self.model}",
            }
        except Exception as exc:
            return {"enabled": True, "reachable": False, "error": str(exc), "model_name": self.model}

    def ask(self, query: str, image_paths: List[str]) -> Optional[Dict[str, Any]]:
        if not self.enabled or not image_paths:
            return None
        parts: List[Dict[str, Any]] = []
        for p in image_paths[:2]:
            jpg = _to_jpeg_base64(p)
            if not jpg:
                return None
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": jpg}})
        parts.append({"text": query})
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM_INSTRUCTION}]},
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200},
        }
        t0 = time.time()
        try:
            r = requests.post(
                f"{_BASE}/{self.model}:generateContent",
                params={"key": self.key},
                json=payload,
                timeout=self.timeout,
            )
        except Exception:
            return None
        latency_ms = int((time.time() - t0) * 1000)
        if not r.ok:
            return None
        try:
            data = r.json()
        except Exception:
            return None
        if data.get("promptFeedback", {}).get("blockReason"):
            return None
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            text = ""
        if not text:
            return None
        return {
            "answer": text,
            "model": self.model,
            "model_name": self.model,
            "model_version": self.model,
            "model_backed": True,
            "model_confidence": float(data["candidates"][0].get("finishReason") == "STOP") if data.get("candidates") else None,
            "fallback_used": False,
            "latency_ms": latency_ms,
            "images_used": len(image_paths[:2]),
            "backend": "google_gemini_free",
            "provider": "Google Gemini (free tier)",
            "warnings": [],
        }