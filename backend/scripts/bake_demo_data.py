#!/usr/bin/env python3
"""Bake synthetic demo datasets into the container image at build time.

Produces GeoTIFFs (and preview PNGs) under /app/data/baked so every Vercel
container instance can restore the demo datasets instantly, even though the
runtime filesystem (/tmp) is ephemeral and per-instance.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, '/app')

from app.demo_data import DEMO_SPECS, bake_all, period_label_for
from app.geo_tools import make_preview

BAKED = Path('/app/data/baked')


def main() -> None:
    bake_all(BAKED)
    for fname, _mod, kind in DEMO_SPECS:
        tif = BAKED / fname
        png = BAKED / (Path(fname).stem + '.png')
        if not png.exists():
            make_preview(tif, png)
        label = period_label_for(kind)
        print(f'baked {fname} ({tif.stat().st_size} bytes) preview={png.exists()} label={label}')


if __name__ == '__main__':
    main()