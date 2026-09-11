# SatQuery AI v4 — Feature Matrix

| Capability | Core ZIP | Optional specialist | Status |
|---|---:|---|---|
| GeoTIFF upload + metadata | Yes | — | Working |
| Natural-language intent routing | Yes | — | Working; tested English/Hinglish/Hindi cases |
| Assam July/Aug flood demo | Yes | optional flood U-Net | Working offline with geo-correct synthetic pair |
| Assam optical + SAR joint demo | Yes | TerraMind task service | Overlapping synthetic optical (S2) + SAR (S1) scenes; fusion route + adapter included |
| Automatic Sentinel-1 retrieval | Yes, requires internet | Planetary Computer STAC | Implemented |
| Temporal SAR flood comparison | Yes | flood U-Net improves masks | Working |
| Persistent water suppression | Yes | — | Working |
| Polygonization + GeoJSON + area | Yes | — | Working |
| Interactive evidence map | Yes | — | Working |
| Urban/bi-temporal change | baseline | Open-CD | Working baseline + trained model adapter |
| Vegetation temporal change | baseline | — | Working baseline |
| Semantic vision assistant | fallback only | TEOChat | Route + bridge included |
| SAR semantic VQA | fallback to TEOChat/baseline | SARChat | Sensor-aware adapter included |
| Very-large-image VQA | fallback to TEOChat/baseline | LRS-VQA | Size-aware adapter included |
| Text-prompt building/road/etc. masks | no fake mask fallback | segment-geospatial / SamGeo | REST adapter included |
| Optical + SAR joint semantic reasoning | TEOChat fallback when connected | TerraMind task service | Multimodal route + adapter included |
| Optical + SAR feature-level fusion | No local foundation model | TerraMind / TerraTorch | Adapter contract included; task model must be deployed |
| Agent execution trace | Yes | optional external planner | Working |
| Confidence/evidence warnings | Yes | — | Working |
| Auth / multi-user RBAC | No | — | Still P1/P2 |
| State-wide tiled/mosaic production processing | No | TerraTorch/tiling can help | Not yet productionized |

| Unsupported capability guard | Yes | — | Working; forecasting/impact/live-alert requests fail safely |
| Result provenance | Yes | — | Working; model/fallback/source scenes shown |
| Confidence breakdown | Yes | — | Working; operational components shown separately |
