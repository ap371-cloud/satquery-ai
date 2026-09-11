# SatQuery AI v4 — Necessary Improvements Only

This build intentionally avoids adding more experimental features. It improves the parts that materially affect correctness and SIH demo trust.

## Added / fixed

1. **Unsupported-capability guard** — future flood/weather forecasting, continuous live alerting, and population/economic impact questions are rejected instead of silently returning image statistics.
2. **Model/data provenance** — every result identifies the actual method/model, whether a fallback was used, and the source scenes/dates/CRS/resolution where available.
3. **Confidence breakdown** — input quality, model support, spatial support, temporal support and evidence coverage are shown separately. These scores are explicitly operational, not calibrated scientific probabilities.
4. **Upstream flood-model benchmark context** — only displayed when the pretrained Sentinel Flood Mapper is actually loaded; upstream held-out metrics are labelled as upstream metrics, not scene-specific accuracy.
5. **Duplicate multimodal inference bug fixed** — an optical+SAR specialist is no longer called a second time while generating the final answer.
6. **Core specialist focus** — TEOChat, Open-CD, SamGeo, and Sentinel Flood Mapper are the recommended model-backed additions. SARChat/LRS-VQA/TerraMind remain optional experimental extensions, not required for the three main demos.
7. **Trust-contract tests** — provenance/confidence consistency and unsupported-query behavior are covered by automated tests.

## Why these are the priority

The current product already has upload, metadata, temporal SAR flood logic, STAC retrieval, GeoJSON, interactive mapping and agent traces. Adding more screens or more model names would not improve the judge-facing proof as much as model provenance, safe capability boundaries, and a few real specialist integrations.
