<p align="center">
  <img src="assets/banner.svg" alt="SatQuery AI Banner" width="100%"/>
</p>

<h1 align="center">🛰️ SatQuery AI — Earth Intelligence Copilot</h1>

<p align="center">
  <b>Natural-language Earth-observation queries &rarr; sensor-aware geospatial workflows &rarr; evidence-backed answers.</b>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white"/></a>
  <a href="#"><img src="https://img.shields.io/badge/frontend-React%2FVite-61dafb.svg?style=flat-square&logo=react&logoColor=white"/></a>
  <a href="#"><img src="https://img.shields.io/badge/API-FastAPI-009688.svg?style=flat-square&logo=fastapi&logoColor=white"/></a>
  <a href="#"><img src="https://img.shields.io/badge/maps-MapLibre-2aa889.svg?style=flat-square&logo=maplibre&logoColor=white"/></a>
  <a href="#"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg?style=flat-square"/></a>
  <a href="#"><img src="https://img.shields.io/badge/LICENSE-MIT-green.svg?style=flat-square"/></a>
</p>

---

## Table of Contents

- [What is SatQuery AI?](#-what-is-satquery-ai)
- [Key Capabilities](#-key-capabilities)
- [Architecture](#-architecture)
- [Demo Workflows](#-demo-workflows)
- [Specialist Model Architecture](#-specialist-model-architecture)
- [Software Preview](#-software-preview)
- [Quick Start](#-quick-start)
- [Automated Validation](#-automated-validation)
- [Optional Specialist Setup](#-optional-specialist-setup)
- [Project Structure](#-project-structure)
- [Important Scientific-Use Note](#-important-scientific-use-note)
- [Key Models](#-key-models)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌍 What is SatQuery AI?

SatQuery AI converts natural-language Earth-observation questions into **sensor-aware geospatial workflows** and returns evidence-backed answers, maps, statistics, vector results and a transparent execution trace.

**Example query:**

```text
Show flooded areas around Assam between July and August 2025.
```

> Parsed → **Intent:** Flood detection · **Location:** Assam, India · **Period 1:** July 2025 · **Period 2:** Aug 2025 · **Preferred sensor:** SAR

---

## ✨ Key Capabilities

- 📥 **GeoTIFF / TIFF / PNG / JPEG upload** — raster metadata (CRS, WGS84 bounds, resolution, bands, dimensions).
- 🗣️ **Natural-language routing** for flood, change, vegetation, VQA, grounding and optical+SAR joint requests.
- 🌐 **Hindi / Hinglish + English** query variants for tested intent families.
- 🛰️ **Automatic Sentinel-1 RTC retrieval** for location + temporal flood queries (when online).
- 🌊 **Temporal flood workflow** with persistent-water suppression (`later water − earlier water`).
- 🔄 **Change detection** with alignment + Otsu thresholding.
- 🌿 **Vegetation-change** detection.
- 📐 **Polygonization, GeoJSON & geospatial area statistics.**
- 🛡️ **Location safety guard** — a Guwahati/Assam query cannot silently run on Indore imagery.
- 🗺️ **Interactive MapLibre evidence map.**
- 🧾 **Execution trace & transparent confidence/warnings.**
- 💾 **SQLite analysis history.**

---

## 🏗️ Architecture

```
                ┌─────────────────────────────────────────────────────────┐
  user query    │  Frontend (React + Vite + MapLibre)                     │
 ─────────────► │  natural-language box · imagery library · live trace    │
                │  evidence map · confidence & provenance                 │
                └────────────────────────────┬────────────────────────────┘
                                             │ HTTP /api/v1
                ┌────────────────────────────▼────────────────────────────┐
                │  FastAPI backend                                         │
                │  query parser → intent/place/date routing                │
                │  dataset validation · modality pairing · safety guard    │
                │  geo tools (alignment, flood/change/vegetation, polygo-) │
                │  nization, GeoJSON, previews) · SQLite history           │
                └───────┬──────────────────────────┬──────────────────────┘
                        │ specialist routers        │ STAC / auto retrieval
                ┌───────▼─────────┐        ┌───────▼─────────┐
                │ optional models │        │ Sentinel-1 RTC  │
                │ TEOChat SARChat │        │ Planetary      │
                │ SamGeo Open-CD  │        │ Computer STAC  │
                │ TerraMind U-Net │        │ (when online)  │
                └────────┬────────┘        └────────┬────────┘
                         └──────────┐   ┌──────────┘
                            evidence-backed answer + map + stats
```

## 🧩 Demo Workflows

Run these fully offline from the UI after clicking **Load offline Assam temporal flood demo**:

| Workflow | Input | What happens |
|---|---|---|
| Temporal SAR flood | Assam July + August SAR | before/after water masks → persistent-water suppression → new inundation area |
| Urban change | 2 Indore optical scenes | aligned abs-diff + Otsu → polygonized change |
| Vegetation loss | 2 optical scenes | excess-green index difference → loss footprint |
| Optical + SAR joint | Assam optical + SAR (overlapping) | TerraMind fusion when connected, semantic TEOChat fallback, else local baseline |
| Single-scene flood | 1 SAR image | adaptive dual-pol water specialist |

---

When a remote-sensing VLM specialist is connected, SatQuery routes queries intelligently:

| Capability | Integration | Fallback |
|---|---|---|
| Temporal + single-image EO VQA | **TEOChat** | image-statistics baseline |
| SAR-domain VQA | **SARChat** | TEOChat, then baseline |
| Very large remote-sensing image VQA | **LRS-VQA** | TEOChat, then baseline |
| Trained change detection | **Open-CD** | aligned abs-diff + Otsu |
| Language-guided geospatial masks | **segment-geospatial / SamGeo** | semantic VQA only |
| Optical + SAR feature-level model | **TerraMind** task service | TEOChat semantic fallback |
| Flood segmentation | optional Sentinel-1 VV/VH U-Net | adaptive dual-pol SAR baseline |

If no VLM is connected, SatQuery **never fakes a semantic answer** — it returns a transparent local image-statistics baseline plus a warning.

> See `SPECIALIST_INTEGRATIONS.md` and `GITHUB_SPECIALIST_SELECTION.md`.

---

## 🖥️ Software Preview

Here is what SatQuery AI looks like in action with its interactive MapLibre evidence map and execution trace:

<p align="center">
  <img src="assets/app-preview.svg" alt="SatQuery AI Software Preview" width="85%"/>
</p>

---


## 🚀 Quick Start

### Windows

**Terminal 1 — Backend:**

```bat
scripts\start_backend.bat
```

**Terminal 2 — Frontend:**

```bat
scripts\start_frontend.bat
```

Then open:

```text
http://localhost:5173
```

### Linux / macOS

```bash
./scripts/start_backend.sh
```

and in another terminal:

```bash
./scripts/start_frontend.sh
```

### Offline demo

With no internet, click **Load offline Assam temporal flood demo** to run the geo-correct synthetic SAR pair (July/August 2025).

---

## 🧪 Automated Validation

```bash
python scripts/test_natural_language.py
python scripts/smoke_test.py
python scripts/test_e2e_matrix.py
```

Covered routes: temporal Assam flood, urban change, vegetation analysis, single-scene flood, wrong-location rejection, offline vision-fallback transparency, TEOChat / SARChat / SamGeo / Open-CD / TerraMind / LRS-VQA contracts, and more.

---

## 🧰 Optional Specialist Setup

```bash
# Flood model (U-Net, Sentinel-1 VV/VH)
cd backend
python -m pip install -r requirements-ml.txt
cd ..
python scripts/setup_flood_model.py

# All specialists
python scripts/setup_specialists.py
```

Environment variables are documented in `backend/.env.example`.

---

## 📂 Project Structure

```
├── backend/            # FastAPI service, EO/geospatial logic, adapters
├── frontend/           # React + Vite + MapLibre UI
├── services/
│   └── teochat_service/# EO-VLM (TEOChat / Qwen2-VL) inference service
├── scripts/            # Bridge, setup, and test scripts
├── demo_data/          # Demo imagery
├── docs/               # PRD, architecture, security, frontend spec
└── assets/             # Branding (logo, banner, preview)
```

---

## ⚠️ Important Scientific-Use Note

This is an **SIH-grade working prototype**, not a certified disaster-response product. Model accuracy depends on chosen checkpoints, preprocessing, sensor conditions and validation data. The UI intentionally distinguishes deterministic fallbacks, specialist-model results and semantic VLM answers instead of presenting all outputs as equally reliable.

---

## 🛠️ Key Models

| Model | Role | Runtime |
|---|---|---|
| **TEOChat** (`jirvin16/TEOChat`, Video-LLaVA 7B) | Primary EO vision-language backend | CUDA |
| **Qwen2-VL-2B-Instruct** | CPU fallback vision-language backend | CPU / CUDA |

Engine selection is deterministic via `TEOCHAT_ENGINE` (`auto | teochat | cpu-vlm`).

---

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development workflow, validation
commands and the project's honesty principles. Community-guide expectations are
in [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md); security reporting guidance is in
[`SECURITY.md`](SECURITY.md).

---

## 📄 License

This project is released under the **MIT License**. See [`LICENSE`](LICENSE) for details.

Copyright &copy; 2026 Naveen Salve.
