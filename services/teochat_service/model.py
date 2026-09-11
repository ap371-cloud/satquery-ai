"""Model runtime for the SatQuery EO-VLM service.

Two backends implement the identical /vqa contract:

* ``teochat``  — official TEOChat checkpoint (jirvin16/TEOChat, Video-LLaVA 7B)
                running in the TEOChat conda environment (CUDA). Ported from
                scripts/teochat_bridge.py.
* ``cpu-vlm``  — a real vision-language model (Qwen/Qwen2-VL-2B-Instruct by
                default) running genuinely on CPU. It is always self-identified
                by its real name and is NEVER presented as TEOChat.

Selection is deterministic and overridable via TEOCHAT_ENGINE :
  auto     -> TEOChat when CUDA + videollava are available, else CPU VLM
  teochat  -> force the TEOChat checkpoint backend
  cpu-vlm  -> force the running-on-CPU transformer backend
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

_STATE: Dict[str, Any] = {
    "started_at": time.time(),
    "model_loaded": False,
    "load_count": 0,
    "inference_count": 0,
    "smoke_inference": False,
    "load_ms": None,
    "last_inference_ms": None,
    "last_error": None,
}
_LOAD_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()
_ENGINE: Dict[str, Any] = {"backend": None}


# --------------------------------------------------------------------------- #
# CPU backend (real VLM through transformers)
# --------------------------------------------------------------------------- #

class CPUVLMBackend:
    name = "cpu-vlm"

    def __init__(self, model_id: Optional[str] = None, max_new_tokens: Optional[int] = None):
        self.model_id = model_id or os.getenv("TEOCHAT_CPU_VLM", "Qwen/Qwen2-VL-2B-Instruct")
        try:
            self.max_new_tokens = int(max_new_tokens or os.getenv("TEOCHAT_MAX_NEW_TOKENS", "192"))
        except (TypeError, ValueError):
            self.max_new_tokens = 192
        self.device = "cuda" if _cuda_available() else "cpu"
        self.dtype = os.getenv("TEOCHAT_DTYPE", "bfloat16")
        self.model = None
        self.processor = None
        self.version = _repo_sha(self.model_id)

    def load(self) -> None:
        if self.model is not None:
            return
        import torch
        from transformers import AutoProcessor
        from transformers import AutoModelForImageTextToText

        dtype = getattr(torch, self.dtype, torch.bfloat16)
        t0 = time.time()
        print(f"[cpu-vlm] loading: {self.model_id} on {self.device} ({self.dtype})", flush=True)
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        try:
            self.model = AutoModelForImageTextToText.from_pretrained(self.model_id, dtype=dtype, low_cpu_mem_usage=True)
        except TypeError:
            self.model = AutoModelForImageTextToText.from_pretrained(self.model_id, torch_dtype=dtype, low_cpu_mem_usage=True)
        self.model = self.model.eval()
        print(f"[cpu-vlm] loaded in {time.time() - t0:.1f}s", flush=True)

    def generate(self, image_paths: List[str], question: str) -> str:
        import torch
        from PIL import Image

        content = []
        images = []
        for p in image_paths:
            img = Image.open(p).convert("RGB")
            images.append(img)
            content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": question})
        conversation = [{"role": "user", "content": content}]
        text = self.processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
        inputs = self.processor(text=[text], images=images, return_tensors="pt")
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        answer = self.processor.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return str(answer).strip()


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# TEOChat backend (real checkpoint, Video-LLaVA stack)
# --------------------------------------------------------------------------- #

class TEOChatBackend:
    name = "teochat"

    def __init__(self):
        self.model_path = os.getenv("TEOCHAT_MODEL", "jirvin16/TEOChat")
        self.device = os.getenv("TEOCHAT_DEVICE", "cuda")
        self.load_8bit = os.getenv("TEOCHAT_LOAD_8BIT", "1").lower() in {"1", "true", "yes"}
        self.dtype = "float16"
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.run_inference_single = None
        self.version = _repo_sha(self.model_path)

    def load(self) -> None:
        from videollava.eval.eval import load_model
        from videollava.eval.inference import run_inference_single

        print(f"[teochat] loading checkpoint {self.model_path} (load_8bit={self.load_8bit})", flush=True)
        self.tokenizer, self.model, self.processor = load_model(
            model_path=self.model_path,
            model_base=None,
            load_8bit=self.load_8bit,
            device=self.device,
        )
        self.model = self.model.eval()
        self.run_inference_single = run_inference_single
        print(f"[teochat] loaded on {self.device}", flush=True)

    def generate(self, image_paths: List[str], question: str) -> str:
        prefix = (
            "These are satellite/earth-observation images in chronological order: <video> "
            if len(image_paths) > 1
            else "This is a satellite/earth-observation image: <video> "
        )
        answer = self.run_inference_single(self.model, self.processor, self.tokenizer, prefix + question.strip(), image_paths)
        return str(answer).strip()


def _repo_sha(model_id: str) -> str:
    """Report the actual upstream checkpoint revision (commit sha) when possible."""
    try:
        from huggingface_hub import model_info
        return str(model_info(model_id).sha or "")
    except Exception:
        return ""


def _make_backend() -> Any:
    engine = os.getenv("TEOCHAT_ENGINE", "auto").strip().lower()
    if engine in {"", "auto"}:
        if _cuda_available():
            return TEOChatBackend()
        return CPUVLMBackend()
    if engine == "teochat":
        return TEOChatBackend()
    if engine == "cpu-vlm":
        return CPUVLMBackend()
    raise RuntimeError(f"Unknown TEOCHAT_ENGINE={engine!r} (use auto|teochat|cpu-vlm)")


# --------------------------------------------------------------------------- #
# Unified runtime
# --------------------------------------------------------------------------- #

def get_engine():
    """Return a loaded backend, loading it exactly once (load_count stays 1)."""
    if _ENGINE["backend"] is not None:
        return _ENGINE["backend"]
    with _LOAD_LOCK:
        if _ENGINE["backend"] is not None:
            return _ENGINE["backend"]
        try:
            backend = _make_backend()
            t0 = time.time()
            backend.load()
        except Exception as exc:
            _STATE["last_error"] = str(exc)
            raise
        _STATE["load_count"] += 1
        _STATE["load_ms"] = int((time.time() - t0) * 1000)
        _STATE["model_loaded"] = True
        _STATE["last_error"] = None
        _ENGINE["backend"] = backend
        return backend


def backend_display_name(backend: Any) -> str:
    if backend.name == "teochat":
        return f"TEOChat ({backend.model_path})"
    return backend.model_id


def run_inference(image_paths: List[str], question: str) -> Dict[str, Any]:
    backend = get_engine()
    t0 = time.time()
    with _INFER_LOCK:
        answer = backend.generate(image_paths, question)
    latency_ms = int((time.time() - t0) * 1000)
    _STATE["inference_count"] += 1
    _STATE["last_inference_ms"] = latency_ms
    return {
        "answer": answer,
        "model_name": backend_display_name(backend),
        "model_version": getattr(backend, "version", "") or "",
        "backend": backend.name,
        "device": backend.device,
        "dtype": backend.dtype,
        "latency_ms": latency_ms,
        "images_used": len(image_paths),
    }


def mark_smoke_ok() -> None:
    _STATE["smoke_inference"] = True


def health() -> Dict[str, Any]:
    backend = _ENGINE["backend"]
    ready = bool(backend) and _STATE["model_loaded"] and _STATE["smoke_inference"]
    return {
        "status": "ready" if ready else ("loading" if _STATE["model_loaded"] else "unavailable"),
        "backend": backend.name if backend else None,
        "model_name": backend_display_name(backend) if backend else None,
        "model_version": getattr(backend, "version", "") if backend else "",
        "model_loaded": _STATE["model_loaded"],
        "smoke_inference": _STATE["smoke_inference"],
        "device": backend.device if backend else None,
        "dtype": backend.dtype if backend else None,
        "load_count": _STATE["load_count"],
        "inference_count": _STATE["inference_count"],
        "load_ms": _STATE["load_ms"],
        "last_inference_ms": _STATE["last_inference_ms"],
        "process_memory_mb": _process_memory_mb(),
        "started_at": _STATE["started_at"],
        "uptime_s": int(time.time() - _STATE["started_at"]),
        "error": _STATE["last_error"],
    }


def _process_memory_mb() -> Optional[float]:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return None