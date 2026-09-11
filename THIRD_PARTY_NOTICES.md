# Third-Party Notices

SatQuery AI integrates or can connect to open-source/public services. Verify licenses and service terms before production deployment.

- **MapLibre GL JS** — BSD-3-Clause. Used for interactive evidence maps.
- **OpenStreetMap tiles/data** — the demo map uses public OSM raster tiles when network access is available; follow OSM tile usage and attribution policies for production traffic.
- **Microsoft Planetary Computer STAC** — used by the automatic Sentinel-1 RTC retrieval module. Follow the service/data terms applicable to your deployment.
- **Sentinel Flood Mapper** by kimbielby — MIT-licensed code/model project. Optional checkpoint setup downloads the `v1.0.0` `best_model.pt` release asset. Architecture: U-Net with EfficientNet-B0 encoder, VV/VH input.
- **Optional external agent bridge** — kept as an integration adapter. It is not shown as the SatQuery product identity in the frontend.

- **TEOChat** — optional temporal/single-image Earth-observation VLM integration. Model/repository terms must be reviewed before deployment.
- **SARChat** — optional SAR-domain VLM integration. Multiple checkpoint families are available; review the selected checkpoint/repository terms before deployment.
- **Open-CD** — optional trained remote-sensing change-detection service. Review selected model/config/checkpoint licenses.
- **segment-geospatial / SamGeo** — optional language-guided geospatial segmentation service. Review the model backend and checkpoint terms in addition to the package license.
- **LRS-VQA** — optional large-remote-sensing-image VQA integration. The project released code/model weights in 2026; review upstream model and base-model licenses before deployment.
- **TerraMind / TerraTorch** — optional multimodal EO foundation-model integration for task-specific optical + SAR workflows. TerraMind's repository is Apache-2.0, but downstream data/model terms should also be reviewed.
