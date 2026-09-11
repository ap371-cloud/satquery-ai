# v2 Implementation Alignment

The current working prototype now supports query parsing for location/time, automatic Sentinel-1 RTC retrieval for temporal flood questions, persistent-water suppression, geospatial polygons/area, interactive map evidence, and optional pretrained SAR flood inference. Large state-level queries use a bounded analysis AOI in the interactive prototype and should be tiled/mosaicked for production.

---

# SatQuery AI — Product Requirements Document (PRD)

**Document Version:** 1.0  
**Project:** SatQuery AI  
**Type:** Agentic Vision-Language Assistant for Earth Observation  
**Primary Goal:** Convert natural-language Earth-observation questions into reliable, evidence-backed remote-sensing workflows.

---

## 1. Product Summary

SatQuery AI is an agentic GeoAI assistant that allows a user to upload or select satellite data and ask questions in natural language.

Instead of relying on a single model, SatQuery AI:

1. Understands the user's intent.
2. Inspects available satellite inputs and metadata.
3. Plans the required analysis.
4. Selects the correct specialist model/tool.
5. Runs geospatial processing.
6. Validates evidence and confidence.
7. Returns a grounded answer with maps, statistics, sources, and visual evidence.

### Core Product Promise

> **Ask Earth. AI Plans. Models Analyze. Evidence Answers.**

---

## 2. Problem

Satellite imagery is valuable for disaster response, urban planning, agriculture, environment monitoring and research, but most existing tools require:

- GIS expertise
- Remote-sensing knowledge
- Understanding of satellite sensors and bands
- Manual model/tool selection
- Multiple disconnected analysis tools
- Manual interpretation of results

Non-expert users often cannot answer simple questions such as:

- What changed between two dates?
- Where did urban construction increase?
- Which areas are flooded?
- How much vegetation was lost?
- Which regions are visible in optical imagery but uncertain due to clouds?
- Should optical or SAR imagery be trusted for this task?

---

## 3. Product Vision

Build a **sensor-aware, evidence-grounded, agentic GeoAI copilot** that converts Earth-observation questions into trustworthy analysis workflows.

SatQuery AI should not behave like a generic image chatbot.

It should behave like a remote-sensing analyst that:

- understands the question,
- understands the data,
- chooses the right analysis method,
- executes the workflow,
- and explains the answer with evidence.

---

## 4. Target Users

### Primary Users

- Disaster management teams
- Urban planners
- Environmental monitoring teams
- Researchers
- Students and non-expert users

### Secondary Users

- Agriculture analysts
- NGOs
- Government field teams
- GIS professionals seeking faster analysis

---

## 5. MVP Use Cases

The MVP will focus on three strong use cases.

### UC-01 — Urban Change Detection

**Example query:**  
“Show where urban construction increased between 2023 and 2026.”

**Expected output:**

- Changed-region overlay
- Built-up area increase %
- Area in km²/hectares
- Highlighted polygons
- Confidence score
- Source image dates
- Analysis trace

---

### UC-02 — Flood Detection Using SAR

**Example query:**  
“Identify flooded areas in this region.”

**Expected behavior:**

- Detect poor optical visibility/cloud cover if applicable
- Prefer SAR when optical imagery is unreliable
- Segment flooded area
- Calculate affected area
- Return map overlay + confidence

---

### UC-03 — Environmental Change

**Example query:**  
“Where was vegetation lost between these two dates?”

**Expected output:**

- Vegetation loss mask
- Area lost
- Percentage change
- Spatial location
- Confidence score
- Source metadata

---

## 6. Core Differentiators

### 6.1 Agentic Geo Planner

The system must create a task plan instead of directly sending every query to one model.

Example:

```text
Query
↓
Intent Detection
↓
Input Validation
↓
Task Planning
↓
Model / Tool Selection
↓
Analysis
↓
Evidence Validation
↓
Grounded Response
```

---

### 6.2 Sensor-Aware Routing

The system should identify and use relevant metadata:

- Sensor type
- Optical / SAR
- Acquisition date
- Resolution
- Bands
- Polarization
- CRS
- Coordinates
- Cloud cover
- spatial extent

Example:

```text
Optical image cloud cover = high
↓
Optical reliability reduced
↓
SAR analysis selected
```

---

### 6.3 Evidence-Grounded Answers

Every analytical answer should provide, where applicable:

- visual evidence,
- spatial evidence,
- statistics,
- confidence,
- source metadata,
- selected method/model.

---

### 6.4 Cross-Modal Verification

For compatible tasks, findings from multiple modalities may be compared.

Example:

```text
Optical finding
+
SAR finding
+
Spatial overlap
↓
Evidence fusion
↓
Final confidence
```

---

### 6.5 What + Where + How Much + Confidence

Every quantitative result should aim to answer:

| Question | Example |
|---|---|
| What? | New built-up region |
| Where? | North-east AOI |
| How much? | +17.8%, 3.42 km² |
| Evidence? | Change polygons |
| Confidence? | 91% |

---

## 7. Functional Requirements

### FR-01 — User Query Input

The user can enter a natural-language question.

**Acceptance criteria:**

- Supports text query
- Query linked to current analysis session
- Empty queries rejected
- Query history retained during session

---

### FR-02 — Satellite Data Upload

Support upload of relevant raster inputs.

**MVP formats:**

- GeoTIFF
- TIFF
- PNG/JPEG for visual-only demo mode

**Preferred full mode:**

- GeoTIFF with metadata
- Sentinel-derived inputs

---

### FR-03 — Metadata Extraction

System extracts available metadata automatically.

Examples:

- CRS
- bounds
- resolution
- band count
- date if available
- sensor if available
- nodata
- raster dimensions

---

### FR-04 — Input Compatibility Check

For multi-temporal analysis, verify:

- overlapping region
- CRS compatibility
- resolution compatibility
- valid timestamps
- image dimensions
- geospatial alignment requirement

---

### FR-05 — Intent Classification

Initial supported intents:

- visual question answering
- change detection
- segmentation
- flood/water detection
- urban/built-up analysis
- vegetation analysis
- SAR analysis
- cross-modal comparison

---

### FR-06 — Task Planning

The agent planner produces a structured plan containing:

- detected intent
- required inputs
- selected tools/models
- processing steps
- expected outputs

---

### FR-07 — Model Routing

The orchestrator selects relevant specialist components.

MVP specialist categories:

- VQA engine
- change detection
- segmentation
- optical analysis
- SAR analysis
- geospatial processor

---

### FR-08 — Geospatial Processing

Support:

- reprojection where needed
- clipping
- raster alignment
- masks
- polygon generation
- area calculation
- bounding regions
- layer generation

---

### FR-09 — Evidence Validation

System evaluates whether the result is sufficiently supported.

Possible outcomes:

- High confidence
- Medium confidence
- Low confidence
- Insufficient evidence

---

### FR-10 — Response Generation

The response must combine:

- natural-language answer
- map/overlay
- statistics
- confidence
- source metadata
- execution summary

---

### FR-11 — Agent Execution Trace

Frontend should display a readable execution trace.

Example:

```text
✓ Intent: Change Detection
✓ Input Validator: 2 images compatible
✓ Planner: 4 steps generated
✓ Model Router: Change model selected
✓ Geo Processor: Area calculated
✓ Validator: Confidence 92%
✓ Response generated
```

---

### FR-12 — Result Export

MVP:

- PNG/map screenshot
- JSON result

P1:

- PDF report
- GeoJSON
- CSV statistics

---

## 8. Non-Functional Requirements

### NFR-01 — Explainability

Important analysis steps should be visible to the user.

### NFR-02 — Reliability

System must not fabricate high-confidence findings when evidence is insufficient.

### NFR-03 — Performance

Target for demo-sized input:

- UI acknowledgement: < 1 second
- Metadata extraction: < 5 seconds
- Common analysis: target < 30–60 seconds
- Long analysis should stream progress

### NFR-04 — Scalability

Architecture should allow specialist models to be deployed independently later.

### NFR-05 — Modularity

AI, GIS, frontend and backend components should remain replaceable.

### NFR-06 — Auditability

Store:

- query
- input references
- selected analysis path
- model/tool names
- confidence
- result timestamps

---

## 9. Confidence Policy

Suggested confidence bands:

| Score | Label |
|---|---|
| 0.85–1.00 | High |
| 0.65–0.84 | Medium |
| 0.45–0.64 | Low |
| <0.45 | Insufficient Evidence |

The exact method used to compute confidence must be documented per model.

Confidence must not be presented as scientifically calibrated unless it actually is.

---

## 10. MVP Scope

### Must Have — P0

- Natural-language query
- GeoTIFF/image input
- Metadata extraction
- Agentic task planner
- Sensor-aware routing
- Change detection
- SAR/water analysis
- Geospatial area calculation
- Evidence-backed answer
- Map visualization
- Confidence output
- Execution trace

### Should Have — P1

- Cross-modal verification
- Better remote-sensing VQA
- Polygon editing
- Report export
- Analysis history
- Comparison slider

### Future — P2

- Large-area processing
- distributed inference
- automatic satellite catalog search
- multi-user collaboration
- alerting/monitoring
- time-series forecasting
- custom organization model registry

---

## 11. Out of Scope for MVP

Avoid building these before the core demo works:

- full global satellite search engine
- dozens of domain-specific use cases
- billing
- complex organization management
- real-time global monitoring
- custom model training platform
- mobile app
- full enterprise GIS replacement

---

## 12. Success Metrics

### Product Metrics

- User can complete all 3 main demos end-to-end.
- System returns geospatial evidence for quantitative queries.
- User does not manually choose models for normal workflows.
- Failed/unsupported questions are handled safely.

### Technical Metrics

- Input compatibility errors are detected.
- Model/tool selection is logged.
- Output masks align correctly with input imagery.
- Area calculation is geospatially valid.
- Confidence is shown consistently.

### Demo Metrics

At least 3 polished scenarios:

1. Urban expansion
2. Flood detection with SAR preference
3. Environmental/vegetation change

---

## 13. Demo Story

### Demo A — Urban Expansion

User asks:

> “Show urban expansion between 2023 and 2026.”

System shows:

- task plan
- change model selection
- mask
- polygons
- +X% built-up
- Y km² changed
- confidence

---

### Demo B — Cloudy Flood Scene

User asks:

> “Where is flooding visible?”

System detects optical limitations and explains:

> “Optical imagery has significant cloud obstruction. SAR analysis was prioritized.”

Then returns:

- flood mask
- affected area
- map
- confidence

---

### Demo C — Cross-Modal Analysis

User asks:

> “Compare optical and SAR evidence for water-covered regions.”

System returns:

- optical result
- SAR result
- overlap
- unified answer
- confidence

---

## 14. Key Risks

| Risk | Mitigation |
|---|---|
| Too many AI models | Freeze P0 model list |
| SAR complexity | Use a narrow, reliable SAR use case |
| Wrong geospatial area | Use projected CRS for area calculations |
| Hallucinations | Evidence gate + confidence |
| Slow inference | Async jobs + progress |
| Misaligned rasters | Preprocessing/registration |
| Overclaiming accuracy | Show limitations and validation data |

---

## 15. Final MVP Definition

SatQuery AI MVP is complete when a user can:

1. Upload compatible satellite data.
2. Ask a natural-language Earth-observation question.
3. See the system plan the analysis automatically.
4. See the selected sensor/model workflow.
5. Receive a visual geospatial result.
6. Receive quantitative statistics where applicable.
7. See confidence and evidence.
8. Understand how the answer was produced.

---

## 16. One-Line Product Definition

> **SatQuery AI is an agentic multimodal Earth-intelligence copilot that transforms natural-language satellite questions into automatically planned, geospatially grounded and evidence-backed answers.**

---

## v3 Implementation Alignment Update

The current E2E implementation now routes natural-language requests across the following capability classes:

- temporal SAR flood mapping,
- optical change detection,
- vegetation change,
- remote-sensing visual question answering,
- temporal visual comparison,
- text-prompt geospatial segmentation/grounding.

Heavy specialist models are integrated as isolated services:

- TEOChat for single/temporal EO VQA,
- Open-CD for trained bi-temporal change detection,
- segment-geospatial/SamGeo for language-guided masks and GeoJSON.

When a specialist is not connected, the product must show the fallback method explicitly and must not present a deterministic baseline as a trained AI model.

### v3.1 Capability Expansion

Additional supported/request-routed capability classes now include:

- SAR-domain semantic VQA via an optional SARChat service,
- very-large remote-sensing image VQA via an optional LRS-VQA service,
- optical + SAR joint analysis via a TerraMind-compatible task service,
- semantic cross-modal fallback via TEOChat when true feature-level fusion is unavailable.

The product must continue to label each result by the method actually used.

## v4 Trust & Capability Requirements

- Unsupported forecasting, continuous live-alerting, and population/economic-impact requests must fail explicitly instead of falling back to generic image statistics.
- Every completed analysis must expose model/tool provenance, fallback status, source-scene metadata, and an operational confidence breakdown.
- Upstream benchmark metrics may be shown only when the corresponding model is actually loaded, and must be labelled as upstream metrics rather than scene-specific accuracy.

