# SatQuery AI — Core Specialist Repositories

Only these four materially improve the primary SIH flows.

## 1. TEOChat — Vision Assistant
Repo: https://github.com/ermongroup/TEOChat

Use for:
- single-image Earth-observation VQA
- temporal visual Q&A
- scene description/classification

Why core: it directly turns SatQuery into a real EO vision assistant instead of an image-statistics fallback.

## 2. Open-CD — Trained Change Detection
Repo: https://github.com/likyoo/open-cd

Use for:
- bi-temporal urban/built-up change masks

Why core: the deterministic absolute-difference baseline is useful for fallback/testing, but a trained change model is needed for a strong real demo.

## 3. segment-geospatial / SamGeo — Text Grounding
Repo: https://github.com/opengeos/segment-geospatial

Use for:
- `Highlight all buildings`
- roads/water/objects to GeoJSON polygons

The upstream project exposes a FastAPI REST API including `POST /segment/text`, so it maps cleanly to SatQuery's existing adapter.

## 4. Sentinel Flood Mapper — SAR Flood Segmentation
Repo: https://github.com/kimbielby/Sentinel-Flood-Mapper

Use for:
- model-backed VV/VH Sentinel-1 water/flood masks
- temporal pre/post flood comparison

The v4 package keeps `scripts/setup_flood_model.py` for downloading the released checkpoint on a networked machine.

## Not core for the SIH MVP

SARChat, LRS-VQA and TerraMind adapters can remain for future experimentation, but they are not required to prove the main product. Do not spend SIH build time deploying them before the four core pieces above work reliably.
