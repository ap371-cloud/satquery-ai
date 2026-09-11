# Changelog

All notable changes to SatQuery AI are tracked here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Frontend
- **v5 professional UI refresh**: dark aurora hero panel, larger typography,
  rounded cards with layered shadows, gradient primary buttons with hover
  effects, segmented output tabs, macOS-style terminal trace, dark
  satellite-style imagery canvases and gradient confidence bars.
- Added favicon and Hermes-grade index metadata (Inter font, theme color).
- Optical + SAR joint-analysis example now auto-selects an overlapping optical
  and SAR demo pair.

### Backend
- Added a geo-correct synthetic **Assam optical demo scene** (`Assam_August_2025_S2_optical_demo.tif`)
  that shares the SAR demo AOI, enabling genuine optical + SAR fusion offline.
- Multimodal fusion picks the first marked optical and first marked SAR dataset
  from the selection and reports the actual detected modalities in its error
  message when validation fails.

### Testing
- Updated demo-count assertions (`smoke_test.py`, `test_e2e_matrix.py`) for the
  new optical demo scene.
- Full backend suite green: natural-language 65/65, E2E matrix 14/14, smoke and
  trust contract PASS. Frontend lint + production build PASS.

### Documentation
- Added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`
  and a GitHub Actions CI workflow.

## [v4]

- Natural-language routing for flood, change, vegetation, VQA, grounding and
  optical + SAR joint requests.
- Sentinel-1 RTC auto retrieval; temporal SAR flood workflow with persistent
  water suppression; polygonization, GeoJSON and area statistics.
- Specialist adapters: TEOChat, SARChat, LRS-VQA, Open-CD, SamGeo, TerraMind
  and optional Sentinel-1 VV/VH U-Net flood checkpoint.
- Location safety guard, confidence breakdown, model/data provenance and
  unsupported-capability guards.