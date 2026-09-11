# SatQuery AI v4 — Fixes & Capability Upgrades

## Natural language

- Expanded parser coverage for English, Hinglish and Hindi flood queries.
- Month/year temporal parsing supports July/August-style queries and ISO/slash dates.
- Added language-grounding intent for buildings, roads, ships, vehicles, bridges, solar panels, farmland, water and more.
- Added semantic vision-question routing.
- Added optical + SAR joint/fusion intent routing.
- Added false-positive guards so phrases like "this image" are not treated as place names.

## Vision assistant

- Added TEOChat service bridge for single-image and temporal EO VQA.
- Added SARChat-aware routing for SAR semantic questions.
- Added LRS-VQA-aware routing for very large satellite imagery.
- When VLMs are offline, the app exposes a local statistics baseline and explicitly warns that it is not semantic VQA.

## Specialist geospatial AI

- Open-CD adapter/bridge for trained bi-temporal change masks.
- segment-geospatial/SamGeo adapter for natural-language geospatial segmentation and GeoJSON polygons.
- TerraMind-compatible adapter for task-specific optical + SAR multimodal EO fusion.
- Optional Sentinel-1 VV/VH U-Net flood checkpoint remains supported.

## Flood workflow

- Uses earlier + later SAR scenes for temporal flood analysis.
- Suppresses persistent water when estimating probable new inundation.
- Keeps probable flood, persistent water and receded-water logic separate.
- Rejects imagery that does not overlap a requested known location.
- Supports automatic Sentinel-1 RTC retrieval for suitable location/date flood queries when network access exists.

## Frontend

- SatQuery branding preserved.
- Runtime panel now reports general VLM, SAR VLM, large-RSI VLM, text grounding, trained change and multimodal-fusion services separately.
- Added optical + SAR joint-analysis sample query; the example now auto-selects the overlapping Assam optical + SAR demo pair.
- Interactive map and evidence outputs retained.

## Multimodal fusion inputs

- Added a geo-correct synthetic Assam optical scene (same AOI/bbox as the SAR demo) so optical + SAR fusion runs on genuinely overlapping inputs instead of reporting a diagnostic error.
- Multimodal fusion now picks the first marked optical and first marked SAR dataset from the selection instead of assuming the first two entries are one of each.
- The modality error now names the actual modalities found so users can correct their selection/upload.

## Testing

- 59 natural-language/guard checks pass.
- Assam E2E smoke test passes.
- 13-route E2E matrix passes, including VLM, SAR VLM, grounding, trained change, multimodal fusion and large-RSI routing contracts.
