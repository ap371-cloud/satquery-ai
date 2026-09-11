# v2 Architecture Update

The implemented architecture adds `query_parser.py` → `satellite_catalog.py` (Sentinel-1 RTC/STAC) → temporal SAR flood processing → persistent-water suppression → WGS84 GeoJSON → MapLibre evidence rendering. `flood_model.py` loads an optional pretrained VV/VH U-Net checkpoint and otherwise exposes a clearly labeled adaptive fallback.

---

# SatQuery AI — Technical Architecture Document

**Version:** 1.0  
**Project:** SatQuery AI

---

## 1. Architecture Goals

The architecture must support:

- natural-language query understanding,
- satellite metadata inspection,
- task planning,
- specialist model routing,
- optical and SAR workflows,
- geospatial processing,
- evidence validation,
- confidence scoring,
- map-ready outputs,
- auditable execution.

The system should be modular enough that individual models can be replaced without rewriting the entire application.

---

## 2. High-Level Architecture

```text
┌─────────────────────────────┐
│        Web Frontend         │
│ React / Next.js + Map UI    │
└──────────────┬──────────────┘
               │ HTTPS / API
               ▼
┌─────────────────────────────┐
│        Backend API          │
│      Python / FastAPI       │
└──────────────┬──────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│              SatQuery Orchestrator           │
│                                              │
│ Query Understanding                          │
│      ↓                                       │
│ Input / Metadata Validator                   │
│      ↓                                       │
│ Agentic Task Planner                         │
│      ↓                                       │
│ Model / Tool Router                          │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│              Specialist Toolbox              │
│                                              │
│ VQA │ Change Detection │ Segmentation        │
│ Optical Analysis │ SAR Analysis │ Grounding  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌─────────────────────────────┐
│     Geospatial Processor    │
│ Rasterio / GDAL / GeoPandas │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Evidence & Confidence Layer │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Grounded Response Generator │
└──────────────┬──────────────┘
               │
               ▼
       Map + Stats + Text
```

---

## 3. Recommended Tech Stack

### Frontend

- React or Next.js
- TypeScript
- Tailwind CSS
- MapLibre GL JS or Leaflet
- Zustand / React Context for client state
- TanStack Query for server state

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn/Gunicorn

### AI / ML

- PyTorch
- Hugging Face Transformers
- timm
- OpenCV
- NumPy
- scikit-image

### Geospatial

- Rasterio
- GDAL
- GeoPandas
- Shapely
- pyproj
- rioxarray/xarray where useful

### Data / Storage

MVP:

- PostgreSQL
- PostGIS
- local/S3-compatible object storage

Possible providers:

- Supabase PostgreSQL
- MinIO
- AWS S3 / Cloudflare R2

### Async Jobs

Recommended for heavier inference:

- Celery + Redis

Alternative lightweight MVP:

- FastAPI BackgroundTasks
- Redis job queue

### Deployment

MVP:

- Docker
- Frontend: Vercel / Railway / container
- Backend: Railway / Render / GPU VM
- Model inference: local GPU, Hugging Face endpoint, RunPod or equivalent if required

---

## 4. Core Components

## 4.1 Frontend Application

Responsibilities:

- file upload
- map visualization
- query interface
- session state
- analysis progress
- layer controls
- result statistics
- confidence display
- execution trace
- export controls

The frontend must never perform privileged AI or storage operations using exposed secrets.

---

## 4.2 API Gateway / Backend

Responsibilities:

- authentication
- upload orchestration
- request validation
- session management
- job creation
- AI pipeline invocation
- result persistence
- secure signed-file URLs
- audit logs

---

## 4.3 Input Manager

Responsible for ingesting satellite inputs.

### Input pipeline

```text
Upload
↓
File Validation
↓
Metadata Extraction
↓
Object Storage
↓
Raster Record Created
↓
Preview / Tile Generation
```

### Metadata structure

```json
{
  "dataset_id": "ds_123",
  "filename": "sentinel_2026.tif",
  "sensor": "Sentinel-2",
  "modality": "optical",
  "acquired_at": "2026-04-17",
  "crs": "EPSG:32643",
  "width": 4096,
  "height": 4096,
  "resolution_m": 10,
  "bands": ["B2", "B3", "B4", "B8"],
  "bounds": [0, 0, 0, 0],
  "cloud_cover": 0.18
}
```

Fields may be `null` when unavailable.

---

## 4.4 Compatibility Validator

Used before temporal/cross-modal analysis.

Validation checks:

- both files readable
- CRS exists
- spatial overlap exists
- dates valid
- resolution manageable
- no corrupted raster
- compatible region
- required bands available

Possible output:

```json
{
  "compatible": true,
  "warnings": [
    "Resolution differs; resampling required."
  ],
  "actions": [
    "reproject",
    "resample",
    "align"
  ]
}
```

---

## 4.5 Query Understanding Layer

Converts natural-language query into structured intent.

Example:

```json
{
  "intent": "urban_change",
  "entities": {
    "from_date": "2023",
    "to_date": "2026",
    "target": "built_up"
  },
  "required_modalities": ["optical"],
  "needs_temporal_comparison": true,
  "needs_area_statistics": true
}
```

Use an LLM only for semantic parsing and planning where useful. Deterministic validation should remain code-based.

---

## 4.6 Agentic Task Planner

The planner transforms intent + dataset metadata into a task graph.

Example:

```json
{
  "plan_id": "plan_901",
  "steps": [
    {
      "id": "s1",
      "tool": "align_rasters",
      "depends_on": []
    },
    {
      "id": "s2",
      "tool": "builtup_segmentation",
      "depends_on": ["s1"]
    },
    {
      "id": "s3",
      "tool": "change_detection",
      "depends_on": ["s2"]
    },
    {
      "id": "s4",
      "tool": "polygonize",
      "depends_on": ["s3"]
    },
    {
      "id": "s5",
      "tool": "area_statistics",
      "depends_on": ["s4"]
    }
  ]
}
```

The planner output must be validated before execution.

---

## 4.7 Model / Tool Registry

Every specialist should be registered with capabilities.

Example:

```python
MODEL_REGISTRY = {
    "change_v1": {
        "task": "change_detection",
        "modalities": ["optical"],
        "requires": ["t1_image", "t2_image"],
        "output": "change_mask"
    },
    "sar_water_v1": {
        "task": "water_segmentation",
        "modalities": ["sar"],
        "requires": ["sar_image"],
        "output": "water_mask"
    }
}
```

This prevents arbitrary model selection.

---

## 4.8 Specialist Components

### A. Remote-Sensing VQA

Purpose:

- answer semantic questions about imagery,
- summarize visual content,
- help with intent-specific understanding.

Important:

A generic VLM should not be treated as ground truth for quantitative geospatial analysis.

---

### B. Change Detection Engine

Input:

- time-1 raster
- time-2 raster

Output:

- change probability/mask
- changed regions
- optional class-specific change

Tasks:

- urban expansion
- vegetation loss
- water change

---

### C. Segmentation Engine

Supported initial classes:

- water
- vegetation
- built-up
- land/background

Output:

- probability map
- binary/class mask
- confidence

---

### D. Optical Analysis Engine

Possible operations:

- RGB interpretation
- NDVI
- NDWI
- built-up indicators
- cloud masking
- multispectral preprocessing

---

### E. SAR Analysis Engine

MVP focus:

- water/flood detection

Possible preprocessing:

- calibration
- speckle filtering
- thresholding/model inference
- terrain correction if necessary for chosen pipeline

Keep MVP SAR scope narrow and reliable.

---

## 4.9 Geospatial Processing Engine

Responsibilities:

- reprojection
- resampling
- clipping
- raster alignment
- polygonization
- union/intersection
- area calculations
- statistics
- bounding boxes
- GeoJSON output

### Critical rule

Area must not be calculated directly from geographic lat/lon degrees.

Use an appropriate projected CRS.

---

## 4.10 Evidence Fusion Engine

For cross-modal cases.

Example inputs:

```json
{
  "optical_confidence": 0.84,
  "sar_confidence": 0.91,
  "spatial_overlap": 0.88
}
```

Possible MVP fusion:

```text
weighted confidence
+
spatial consistency
+
quality penalties
```

Do not call this a scientifically calibrated confidence model unless validated.

---

## 4.11 Evidence Gate

Before result generation, evaluate:

- result exists
- model confidence
- input quality
- spatial consistency
- required evidence available
- warnings

Possible states:

```text
PASS_HIGH
PASS_MEDIUM
PASS_LOW
REJECT_INSUFFICIENT_EVIDENCE
```

---

## 4.12 Response Generator

Input:

- query
- execution summary
- statistics
- warnings
- confidence
- source metadata
- GeoJSON layers

Output:

```json
{
  "answer": "Built-up area increased...",
  "confidence": 0.91,
  "confidence_label": "High",
  "statistics": {
    "change_percent": 17.8,
    "changed_area_km2": 3.42
  },
  "layers": [],
  "evidence": [],
  "warnings": [],
  "execution_trace": []
}
```

The LLM should verbalize computed facts, not invent them.

---

## 5. Request Flow

```text
1. User uploads raster(s)
2. Backend validates file
3. Metadata extracted
4. Dataset stored
5. User asks question
6. Query parsed
7. Required input check
8. Task plan generated
9. Plan validated
10. Models/tools executed
11. Geo processing runs
12. Evidence validated
13. Response generated
14. Result saved
15. Frontend renders map + stats + trace
```

---

## 6. Suggested API Design

### Authentication

```http
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

### Datasets

```http
POST /api/v1/datasets
GET  /api/v1/datasets
GET  /api/v1/datasets/{id}
DELETE /api/v1/datasets/{id}
```

### Analysis

```http
POST /api/v1/analyses
GET  /api/v1/analyses/{id}
GET  /api/v1/analyses/{id}/status
GET  /api/v1/analyses/{id}/result
```

### Sessions

```http
POST /api/v1/sessions
GET  /api/v1/sessions/{id}
GET  /api/v1/sessions/{id}/queries
```

### Map Layers

```http
GET /api/v1/results/{id}/layers
GET /api/v1/results/{id}/geojson
```

---

## 7. Analysis Job State Machine

```text
QUEUED
↓
VALIDATING_INPUT
↓
PLANNING
↓
PREPROCESSING
↓
RUNNING_MODELS
↓
GEO_PROCESSING
↓
VALIDATING_EVIDENCE
↓
GENERATING_RESPONSE
↓
COMPLETED
```

Failure states:

```text
FAILED_VALIDATION
FAILED_MODEL
FAILED_PROCESSING
CANCELLED
```

---

## 8. Database Schema

### users

```text
id
email
password_hash / auth_provider_id
role
created_at
```

### datasets

```text
id
user_id
filename
storage_key
modality
sensor
acquired_at
crs
metadata_json
created_at
```

### sessions

```text
id
user_id
title
created_at
```

### analyses

```text
id
session_id
user_id
query
intent
status
plan_json
confidence
created_at
completed_at
```

### analysis_inputs

```text
analysis_id
dataset_id
input_role
```

### results

```text
id
analysis_id
answer
statistics_json
evidence_json
warnings_json
created_at
```

### layers

```text
id
result_id
layer_type
storage_key
geojson / metadata
```

### audit_logs

```text
id
user_id
action
resource_type
resource_id
metadata_json
created_at
```

---

## 9. Storage Strategy

Store raw uploads separately from derived artifacts.

```text
/raw/{user_id}/{dataset_id}/...
/processed/{analysis_id}/...
/results/{analysis_id}/...
/previews/{dataset_id}/...
```

Use signed URLs for protected objects.

---

## 10. Model Serving Options

### Option A — Single Backend MVP

All models loaded in one Python service.

**Pros:** simple  
**Cons:** memory-heavy

### Option B — Model Microservices

```text
API
├─ orchestrator
├─ change-service
├─ segmentation-service
└─ sar-service
```

Use only if team has enough time.

### Recommended

Start monolithic/modular for SIH prototype, then split services later.

---

## 11. Remote-Sensing Adaptation Layer

Suggested approach:

```text
Base vision-language model
↓
Remote-sensing dataset
↓
PEFT / LoRA adaptation
↓
Remote-sensing VQA model
```

Potential datasets/models must be selected according to licensing, compute budget, task suitability and demo requirements.

The product architecture must allow replacing the VQA model without changing the planner.

---

## 12. Observability

Log:

- request ID
- user ID
- analysis ID
- selected intent
- selected tool/model
- model version
- processing duration
- failure reason
- confidence
- warnings

Metrics:

- analysis latency
- failure rate
- model inference time
- job queue size
- storage usage

---

## 13. Error Handling

### Unsupported Query

Return:

```text
This request is outside the currently supported analysis capabilities.
```

### Missing Inputs

Example:

```text
This analysis requires two temporally different images of an overlapping region.
```

### Poor Evidence

```text
The available imagery does not provide sufficient evidence for a reliable answer.
```

### Model Failure

Use fallback only if a compatible fallback is registered.

Never silently switch to an unrelated model.

---

## 14. Recommended Repository Structure

```text
satquery-ai/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── lib/
│   └── types/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── datasets/
│   │   ├── orchestrator/
│   │   ├── planners/
│   │   ├── models/
│   │   ├── geo/
│   │   ├── evidence/
│   │   ├── jobs/
│   │   └── db/
│   └── tests/
│
├── ml/
│   ├── change_detection/
│   ├── segmentation/
│   ├── sar/
│   └── vqa/
│
├── infra/
│   ├── docker/
│   └── deployment/
│
└── docs/
```

---

## 15. Architecture Decision Summary

### Use FastAPI

Because Python integrates directly with remote-sensing and ML libraries.

### Use PostGIS

Because spatial data will become first-class product data.

### Use object storage

Raster files are not suitable for direct database storage.

### Keep planner + deterministic tools separate

LLMs may plan; geospatial calculations must be deterministic.

### Keep MVP monolithic

Faster development and debugging for SIH.

---

## 16. Final Technical Principle

> **LLM decides what to do; deterministic geospatial tools and specialist models determine what actually happened.**

---

## v3 Specialist-Service Architecture

To avoid incompatible CUDA/Torch/OpenMMLab dependencies inside the main GIS API, specialist research models run as isolated HTTP services.

```text
FastAPI Orchestrator
├── TEOCHAT_URL  -> EO Vision Assistant / Temporal VQA
├── OPENCD_URL   -> Trained Change Detection
├── SAMGEO_URL   -> Text-Prompt Geospatial Segmentation
└── Local Tools  -> Rasterio/GIS/Flood/NDVI/Fallbacks
```

The main backend owns authorization, query parsing, dataset validation, geospatial normalization, evidence output and fallback policy. A specialist service only returns model-specific semantic or pixel outputs.

### v3.1 Expanded Specialist Registry

```text
FastAPI Orchestrator
├── TEOCHAT_URL   -> General + temporal EO VQA
├── SARCHAT_URL   -> SAR semantic VQA
├── LRSVQA_URL    -> Very-large RSI VQA
├── OPENCD_URL    -> Trained change detection
├── SAMGEO_URL    -> Text-prompt geospatial segmentation
├── TERRAMIND_URL -> Task-specific optical + SAR multimodal fusion
└── Local GIS/ML fallbacks
```

Routing policy:

1. SAR semantic question → try SARChat, then TEOChat.
2. Very-large raster semantic question → try LRS-VQA before generic VQA.
3. Optical + SAR joint request → require overlapping optical and SAR inputs; try TerraMind task service, then semantic two-image VQA fallback.
4. Quantitative masks/areas remain grounded in specialist pixel outputs or deterministic GIS tools rather than VLM prose.

## v4 Trust Layer Additions

The response pipeline now includes a capability guard before execution and a provenance builder after evidence validation. The final result schema includes `provenance` and `confidence_breakdown`. External specialist inference must occur only once per analysis; final-answer generation consumes the already-produced structured result rather than re-calling a model.

