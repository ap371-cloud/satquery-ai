"""Demo preflight: prepares and verifies the model-backed Vision runtime.

Modes
-----
  python scripts/demo_preflight.py                 # prepare data + verify service
  python scripts/demo_preflight.py --prepare-only  # just (re)generate demo scenes

Exits non-zero with a clear message when the VLM service is not genuinely
usable, so an honest Vision-READY claim can never rest on a dead endpoint.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
VISION = ROOT / "demo_data" / "vision"
SERVICE_URL = os.getenv("TEOCHAT_URL", "http://127.0.0.1:8021").rstrip("/")
LOAD_TIMEOUT = int(os.getenv("SATQUERY_VLM_RELOAD_TIMEOUT", "900"))


def stage():
    from scripts.make_vision_demo import generate_all
    out = generate_all()
    print(f"[preflight] demo vision scenes ready: {len(out)} semantic + negatives in {VISION.name}")


def _get(path, timeout=8):
    return requests.get(SERVICE_URL + path, timeout=timeout).json()


def verify_service() -> dict:
    print(f"[preflight] service: {SERVICE_URL}")
    try:
        h = _get("/health")
    except requests.RequestException as exc:
        print(f"[preflight] FAIL — VLM service is not reachable at {SERVICE_URL}: {exc}")
        print("           Start it:  python services/teochat_service/app.py")
        sys.exit(3)

    label = h.get("model_name") or "unknown model"
    if h.get("model_loaded"):
        print(f"[preflight] model loaded: {label} (backend={h.get('backend')})")
    else:
        print(f"[preflight] model not loaded yet ({h.get('status')}); triggering a real load + smoke inference ...")
        s = requests.post(SERVICE_URL + "/smoke", timeout=LOAD_TIMEOUT + 120)
        if not s.ok:
            print("[preflight] FAIL — smoke inference failed:", s.text[:400])
            sys.exit(4)
        h = _get("/health")

    if not h.get("smoke_inference"):
        print("[preflight] running real smoke inference (warm-up, ~1-2 min on CPU) ...")
        s = requests.post(SERVICE_URL + "/smoke", timeout=LOAD_TIMEOUT)
        s.raise_for_status()
        body = s.json()
        print(f"[preflight] smoke ok: latency_ms={body.get('latency_ms')} (model={body.get('model_name')})")

    h = _get("/health")
    ready = h.get("status") == "ready" and h.get("model_loaded") and h.get("smoke_inference")
    print(f"[preflight] health: status={h.get('status')} ready={ready} backend={h.get('backend')}")
    if not ready:
        print("[preflight] FAIL — service did not reach a genuinely ready state.")
        sys.exit(5)

    smoke_path = VISION / "vision_sample.tif"
    if not smoke_path.exists():
        print("[preflight] FAIL — demo scenes missing; run without --prepare-only first.")
        sys.exit(6)

    print("[preflight] PASS — model-backed vision runtime verified ready.")
    return h


if __name__ == "__main__":
    if "--prepare-only" in sys.argv:
        stage()
        sys.exit(0)
    stage()
    verify_service()