"""Verify only the specialist services that materially improve SatQuery's main demos.

Core recommended specialists:
1) TEOChat — single/temporal EO vision assistant
2) Open-CD — trained bi-temporal change detection
3) segment-geospatial/SamGeo — language-guided geospatial grounding
4) Sentinel Flood Mapper checkpoint — model-backed SAR flood masks

The rest of the experimental adapters are optional and are not required for the
three SIH golden demos.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.flood_model import model_status

services = {
    'TEOChat vision assistant': os.getenv('TEOCHAT_URL',''),
    'Open-CD change detector': os.getenv('OPENCD_URL',''),
    'SamGeo text grounding': os.getenv('SAMGEO_URL',''),
}
print('SATQUERY CORE SPECIALIST READINESS')
print('==================================')
print('Flood model:', json.dumps(model_status(), indent=2))
for name, url in services.items():
    if not url:
        print(f'{name}: NOT CONFIGURED')
        continue
    try:
        r=requests.get(url.rstrip('/')+'/health', timeout=3)
        print(f'{name}:', 'READY' if r.ok else f'HTTP {r.status_code}', '-', r.text[:240])
    except Exception as exc:
        print(f'{name}: UNREACHABLE - {exc}')
