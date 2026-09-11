# GitHub Specialist Selection — Why These Repositories

This file documents which external open-source projects were selected for SatQuery AI and which capability gap each one closes.

| Gap in SatQuery core | Selected project | Why selected | Runtime status |
|---|---|---|---|
| Semantic remote-sensing vision assistant | `ermongroup/TEOChat` | Built specifically for temporal Earth-observation VQA and also reports strong single-image EO VQA | Adapter + bridge included |
| SAR-specific semantic understanding | `JimmyMa99/SARChat` | SAR-focused VLM/data/models for captioning, VQA, counting, grounding | Adapter included |
| Trained bi-temporal change detection | `likyoo/open-cd` | Mature remote-sensing change-detection toolbox with multiple model families | Adapter + bridge included |
| Text-prompt geospatial masks | `opengeos/segment-geospatial` | Georeferenced SAM workflow, text-prompt segmentation, GeoJSON output | REST adapter included |
| Very large satellite-image VQA | `VisionXLab/LRS-VQA` | Coarse-to-fine perception for very large remote-sensing images, model weights released | Large-RSI adapter included |
| Optical + SAR multimodal foundation model / fine-tuning | `IBM/terramind` | EO-native multimodal foundation model; official Sen1Floods11 config uses Sentinel-2 + Sentinel-1 modalities | Fusion-service adapter included |

## Why GeoChat is not the primary VQA route

GeoChat remains a strong grounded RS VLM, but TEOChat is used as the default general/temporal vision assistant because the TEOChat project reports stronger single-image performance than GeoChat on several zero-shot scene-classification/VQA tasks while also handling temporal EO sequences.

## Important packaging decision

Large model repositories and weights are **not copied into this ZIP**. Their environments can conflict and model weights are large. SatQuery instead ships stable service adapters/bridges and explicit runtime health checks. This avoids pretending a model is installed when it is not.
