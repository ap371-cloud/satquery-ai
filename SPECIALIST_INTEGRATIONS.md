# SatQuery AI v4 — Specialist Model Integrations

SatQuery keeps heavy research models in separate services so their pinned Torch / CUDA / OpenMMLab environments do not break the main FastAPI + GIS runtime.

## 1. Remote-Sensing Vision Assistant — TEOChat

**Use for:**
- single-image remote-sensing VQA
- image description / scene interpretation
- two-image and temporal EO reasoning
- natural-language questions over temporal image sequences

SatQuery integration:

```text
backend/app/specialist_adapters.py -> TEOChatAdapter
scripts/teochat_bridge.py          -> local HTTP bridge
TEOCHAT_URL                         -> service URL
```

If unavailable, SatQuery falls back to local image statistics and clearly warns that a semantic VLM was not used.

## 2. SAR Semantic Vision Assistant — SARChat

**Use for:**
- SAR image captioning
- SAR-domain VQA
- counting / spatial interpretation in SAR scenes

SatQuery integration:

```text
backend/app/specialist_adapters.py -> SARChatAdapter
SARCHAT_URL                         -> SARChat-compatible /vqa service
```

SatQuery prefers SARChat for semantic questions when the selected raster is marked SAR. If it is unavailable, TEOChat is tried next.

## 3. Large Remote-Sensing Image VQA — LRS-VQA

**Use for:**
- very large satellite images where downsampling can remove small objects/details
- coarse-to-fine VQA on large remote-sensing imagery

SatQuery integration:

```text
backend/app/specialist_adapters.py -> LargeRSVQAAdapter
LRSVQA_URL                         -> compatible /vqa service
SATQUERY_LARGE_RSI_THRESHOLD       -> default 4096 px
```

When the source raster's longest side is above the threshold, SatQuery tries the large-RSI specialist before generic VQA.

## 4. Trained Change Detection — Open-CD

**Use for:**
- bi-temporal optical change masks
- urban / building change detection

SatQuery integration:

```text
backend/app/specialist_adapters.py -> OpenCDAdapter
scripts/opencd_bridge.py           -> isolated Open-CD service
OPENCD_URL                         -> service URL
```

When offline, SatQuery uses its deterministic aligned image-difference baseline and marks it as a baseline.

## 5. Language-Guided Geospatial Segmentation — segment-geospatial / SamGeo

**Use for natural language such as:**

```text
Highlight all buildings in this image.
Where are the roads?
Count the buildings.
Mark the solar panels.
```

SatQuery calls the package's text segmentation REST endpoint and consumes GeoJSON polygons.

```text
SAMGEO_URL=http://127.0.0.1:<port>
```

If segmentation is unavailable but a VLM is online, SatQuery may answer semantically but explicitly states that no pixel-grounded mask was generated.

## 6. Optical + SAR Multimodal Foundation Model — TerraMind

**Use for:**
- task-specific optical + SAR feature-level fusion
- multimodal Earth-observation fine-tuning
- Sentinel-1 + Sentinel-2 downstream segmentation workflows

SatQuery integration:

```text
backend/app/specialist_adapters.py -> TerraMindAdapter
TERRAMIND_URL                      -> task-specific /fusion service
```

Important: TerraMind is a multimodal EO foundation model, not a drop-in chat endpoint. SatQuery therefore expects a **task-specific TerraTorch/TerraMind service** behind `/fusion`. If it is offline, SatQuery can still send both previews to TEOChat for semantic cross-modal reasoning, but it clearly labels that as a fallback rather than feature-level TerraMind fusion.

## 7. Flood Specialist

The existing optional Sentinel-1 VV/VH U-Net remains the preferred flood-water mask model. If its checkpoint/dependencies are missing, the temporal logic still runs with an adaptive dual-polarisation SAR baseline and labels the fallback honestly.

## Why separate services?

TEOChat, Open-CD, LRS-VQA, TerraMind/TerraTorch, SARChat, and modern SAM stacks can require mutually incompatible package versions. HTTP bridges preserve a stable E2E app while allowing each specialist to run in its officially recommended environment.
