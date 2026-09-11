"""One-command optional model setup.

Downloads the MIT-licensed pretrained Sentinel Flood Mapper v1.0.0 checkpoint.
Install backend/requirements-ml.txt first (or pass --install-deps).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MODEL_DIR = BACKEND / "models"
MODEL = MODEL_DIR / "best_model.pt"
URL = "https://github.com/kimbielby/Sentinel-Flood-Mapper/releases/download/v1.0.0/best_model.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install-deps", action="store_true", help="Install PyTorch + segmentation-models-pytorch from requirements-ml.txt")
    args = ap.parse_args()
    if args.install_deps:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(BACKEND / "requirements-ml.txt")])
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL.exists() and MODEL.stat().st_size > 1_000_000:
        print(f"Model already exists: {MODEL}")
        return
    print("Downloading pretrained flood checkpoint…")
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with MODEL.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    print(f"Saved: {MODEL} ({MODEL.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
