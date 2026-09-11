# SatQuery AI — Frontend Specification v2

## 1. Product UI Goal

The frontend must make satellite analysis understandable without forcing the user to operate GIS tools manually. The hero interaction remains a simple two-column research workflow.

```text
LEFT                                       RIGHT
Natural-language question                  Final grounded answer
Parsed location/date/sensor chips          Execution trace
Auto retrieval / upload imagery            Interactive map / evidence image
Earlier + later input                      GeoJSON / image export
Analyze / Clear                            Confidence / method / warnings
Sample queries
```

## 2. Branding

User-facing identity:

**SatQuery AI**  
**Agentic Multimodal Earth Intelligence**  
**Ask Earth. AI Plans. Models Analyze. Evidence Answers.**

Third-party frameworks/models are attributed in documentation and runtime metadata, not used as the main product identity.

## 3. Query Composer

Required:

- large natural-language textarea,
- placeholder with a real geospatial example,
- debounced query parsing,
- visible parsed context chips:
  - location,
  - date range,
  - preferred sensor,
  - automatic satellite retrieval readiness.

Example:

```text
Show flooded areas around Assam between July and August 2025.
```

Parsed UI:

```text
Assam, India
2025-07-01 → 2025-08-31
SAR
Auto satellite retrieval ready
```

## 4. Satellite Input

### Manual mode

Primary/earlier image card:

- preview,
- filename,
- modality,
- acquisition date,
- CRS,
- resolution,
- dimensions,
- replace/remove actions.

Comparison/later image:

- optional for generic tasks,
- required for temporal change/flood workflow,
- clearly labeled later image.

### Query-driven mode

When no raster is selected and the query contains a supported location + temporal range:

```text
No upload needed
SatQuery will retrieve matching Sentinel-1 scenes when you submit.
```

## 5. Synthetic Demo Label

Offline demo imagery must never look like observed satellite truth.

Every synthetic raster displays:

```text
SYNTHETIC DEMO DATA
```

## 6. Main Actions

Primary action changes based on state:

```text
Analyze
```

or

```text
Retrieve & Analyze
```

Processing states:

- Understanding request
- Planning workflow
- Preparing imagery
- Running specialist tools
- Geospatial processing
- Validating evidence
- Completed / Failed

## 7. Final Answer

The answer card includes:

- natural-language answer,
- operational confidence,
- method/tool information,
- copy action.

Confidence wording:

```text
Medium operational confidence · 79%
```

Never label the score as a calibrated scientific probability unless calibration is actually implemented.

## 8. Execution Trace

Structured events only; no private chain-of-thought.

Examples:

```text
✓ Query understood
✓ Satellite retrieval started
✓ Sentinel-1 scene ready
✓ Sensor-aware routing
✓ Task plan created
✓ Temporal SAR flood workflow
✓ Geospatial processing complete
✓ Evidence gate complete
✓ Grounded response generated
```

Warnings/errors use distinct status icons.

## 9. Geospatial Evidence Panel

Tabs:

### Interactive Map

MapLibre GL JS:

- pan/zoom,
- metric scale,
- georeferenced analysis overlay,
- WGS84 GeoJSON polygons,
- polygon click popup with area,
- optional OSM raster basemap.

### Evidence Image

- annotated overlay,
- download PNG,
- download GeoJSON.

Flood legend:

- probable new inundation,
- persistent water,
- receded water.

## 10. Evidence Cards

Below hero workflow show:

- Parsed request
- Input source
- Flood inference/model status
- Evidence gate
- Geo outputs

## 11. Statistics

For temporal flood result:

- before water %
- after water %
- probable new flood %
- probable flood area km²
- persistent water area km²
- receded water area km²

## 12. Runtime Panel

Secondary/advanced control only.

Show:

- Core API health
- Pretrained flood model readiness vs adaptive fallback
- Optional external agent bridge status

Do not make implementation dependencies the main brand.

## 13. Sample Queries

1. Assam temporal flood / auto retrieval
2. Urban expansion
3. Vegetation loss
4. Image understanding

## 14. Responsive Behavior

Desktop: two columns.

Mobile/tablet:

```text
Question / Input
↓
Answer / Trace
↓
Map / Evidence
```

No horizontal dashboard dependency.

## 15. Accessibility

- keyboard-accessible buttons,
- visible focus states,
- high text contrast,
- statuses not encoded by color alone,
- alt labels for imagery,
- readable failure messages.

## 16. Final Frontend Principle

> The user asks the Earth-observation question; SatQuery shows what data it used, what workflow it ran, where the evidence is, and how uncertain the result is.

---

## v3 Frontend Additions

The Runtime panel now reports specialist availability for:

- Remote-Sensing Vision Assistant,
- Text Grounding / Segmentation,
- Trained Change Detection,
- Flood Model.

Query chips expose parsed target object, preferred sensor, location/date context and vision-assistant routing. Sample prompts include single-image VQA, temporal VQA and language-guided building segmentation.

### v3.1 Runtime & Query UI Additions

Runtime status must separately expose:

- TEOChat general/temporal VQA,
- SARChat SAR VQA,
- LRS-VQA large-image VQA,
- SamGeo text grounding,
- Open-CD trained change detection,
- TerraMind optical+SAR task service.

Query-context chips include an `Optical + SAR joint route` indicator for multimodal requests.

## v4 Result Trust UI

The result view must display: actual model/method, whether fallback was used, source scenes/dates, operational-confidence components, and a clear unsupported-capability message. Confidence components must not be styled or worded as calibrated scientific probabilities.

