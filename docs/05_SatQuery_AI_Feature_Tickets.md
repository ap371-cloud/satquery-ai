# v2 Ticket Status Update

Completed in the current prototype: natural-language Assam/date parsing, location mismatch guard, Sentinel-1 RTC auto retrieval, two-date SAR flood comparison, persistent-water suppression, GeoJSON/area output, interactive MapLibre map, optional pretrained SAR model integration, correct Assam demo geolocation and SatQuery-only frontend branding. See `../FEATURE_MATRIX.md` for exact status.

---

# SatQuery AI — Feature Ticket List

**Version:** 1.0  
**Project:** SatQuery AI

---

## 1. Priority Definitions

### P0 — Must Have

Required for working SIH MVP and main demo.

### P1 — Should Have

Strong enhancement after P0 is stable.

### P2 — Future / Nice to Have

Do not build until core demo works.

---

# EPIC 1 — Project Foundation

## SAT-001 — Create Monorepo Structure

**Priority:** P0  
**Owner:** Full Stack / Tech Lead

### Tasks

- create frontend app
- create FastAPI backend
- create `/ml` modules
- create `/docs`
- create environment templates
- add linting/formatting

### Acceptance Criteria

- frontend runs
- backend runs
- health endpoint works
- project starts using documented commands

---

## SAT-002 — Dockerize Backend

**Priority:** P0

### Acceptance Criteria

- backend builds via Docker
- environment variables injected at runtime
- container runs as non-root where practical
- health check works

---

## SAT-003 — Configure Database

**Priority:** P0

### Acceptance Criteria

- PostgreSQL connection works
- migrations configured
- base tables created

---

# EPIC 2 — Authentication & Access

## SAT-010 — Implement User Authentication

**Priority:** P0

### Acceptance Criteria

- login works
- logout works
- protected routes reject unauthenticated users
- current user endpoint works

---

## SAT-011 — Implement Resource Ownership

**Priority:** P0

### Acceptance Criteria

- dataset has owner
- analysis has owner
- user cannot access another user's private resource

---

## SAT-012 — Add Admin Role

**Priority:** P1

### Acceptance Criteria

- backend-enforced admin role
- admin-only endpoints protected
- admin actions logged

---

# EPIC 3 — Dataset Upload & Metadata

## SAT-020 — Build Dataset Upload UI

**Priority:** P0  
**Owner:** Frontend

### Acceptance Criteria

- upload button
- progress indicator
- errors displayed
- returned dataset shown in sidebar

---

## SAT-021 — Implement Raster Upload API

**Priority:** P0  
**Owner:** Backend

### Acceptance Criteria

- accepted formats validated
- size limit enforced
- dataset stored
- DB record created

---

## SAT-022 — Extract Raster Metadata

**Priority:** P0  
**Owner:** GIS

### Metadata

- CRS
- bounds
- width/height
- resolution
- band count
- nodata
- modality if known

### Acceptance Criteria

- metadata persisted
- malformed raster fails safely

---

## SAT-023 — Generate Raster Preview

**Priority:** P0

### Acceptance Criteria

- preview generated
- frontend can display thumbnail
- large raw raster not downloaded for every preview

---

## SAT-024 — Detect Basic Optical Quality

**Priority:** P1

### Acceptance Criteria

- cloud/quality metric available when supported
- warnings surfaced to planner

---

# EPIC 4 — Dataset Compatibility

## SAT-030 — Implement Spatial Overlap Check

**Priority:** P0

### Acceptance Criteria

- overlap calculated from geospatial bounds
- zero-overlap inputs rejected for temporal analysis

---

## SAT-031 — Implement CRS Compatibility Check

**Priority:** P0

### Acceptance Criteria

- same CRS detected
- differing CRS creates reprojection action

---

## SAT-032 — Implement Resolution Compatibility Check

**Priority:** P0

### Acceptance Criteria

- resolution difference detected
- resampling action generated

---

## SAT-033 — Build Compatibility UI

**Priority:** P0

### Acceptance Criteria

Frontend displays:

- overlap
- CRS
- date availability
- warnings
- planned auto-fixes

---

# EPIC 5 — Natural Language Query

## SAT-040 — Build Query Composer

**Priority:** P0

### Acceptance Criteria

- text query input
- selected dataset chips
- analyze button
- loading state

---

## SAT-041 — Implement Query API

**Priority:** P0

### Acceptance Criteria

- accepts session + datasets + query
- creates analysis record
- returns analysis ID

---

## SAT-042 — Implement Intent Parser

**Priority:** P0  
**Owner:** AI/ML

### Initial intents

- urban_change
- vegetation_change
- flood_detection
- vqa
- sar_analysis
- cross_modal_analysis

### Acceptance Criteria

- intent returned in structured JSON
- unsupported requests handled

---

# EPIC 6 — Agentic Planner

## SAT-050 — Define Tool Registry

**Priority:** P0

### Registered tools

- align_rasters
- reproject
- resample
- change_detection
- water_segmentation
- builtup_segmentation
- vegetation_analysis
- polygonize
- area_statistics
- evidence_validation

### Acceptance Criteria

- each tool has input/output schema
- planner cannot invoke unknown tools

---

## SAT-051 — Build Task Plan Schema

**Priority:** P0

### Acceptance Criteria

Plan includes:

- step ID
- tool
- dependencies
- input references
- validated params

---

## SAT-052 — Implement Agent Planner

**Priority:** P0

### Acceptance Criteria

- takes intent + metadata
- returns ordered plan
- plan can be executed without manual model choice

---

## SAT-053 — Implement Plan Validator

**Priority:** P0

### Acceptance Criteria

Reject plan when:

- tool unknown
- input missing
- resource unauthorized
- dependency invalid
- parameter outside limits

---

# EPIC 7 — Geospatial Preprocessing

## SAT-060 — Implement Raster Reprojection

**Priority:** P0

### Acceptance Criteria

- raster can be reprojected
- output metadata valid

---

## SAT-061 — Implement Raster Alignment

**Priority:** P0

### Acceptance Criteria

- temporal images align to common grid
- output dimensions consistent

---

## SAT-062 — Implement Raster Resampling

**Priority:** P0

### Acceptance Criteria

- target resolution defined
- correct interpolation chosen by data type

---

## SAT-063 — Implement AOI Clipping

**Priority:** P1

---

# EPIC 8 — Urban Change Analysis

## SAT-070 — Implement Built-Up Segmentation

**Priority:** P0  
**Owner:** AI/ML

### Acceptance Criteria

- returns mask/probability
- output aligns with raster
- inference metadata stored

---

## SAT-071 — Implement Bi-Temporal Change Detection

**Priority:** P0

### Acceptance Criteria

- accepts time-1/time-2 aligned inputs
- returns change mask
- works on demo dataset

---

## SAT-072 — Convert Change Mask to Polygons

**Priority:** P0  
**Owner:** GIS

### Acceptance Criteria

- polygon GeoJSON generated
- invalid geometries repaired or rejected

---

## SAT-073 — Calculate Changed Area

**Priority:** P0

### Acceptance Criteria

Returns:

- km²
- hectares
- percent change

Area calculated using valid projected CRS.

---

# EPIC 9 — SAR Flood Analysis

## SAT-080 — Implement SAR Preprocessing Pipeline

**Priority:** P0/P1 depending dataset  
**Owner:** SAR/ML

### Acceptance Criteria

- selected demo SAR data can be normalized/prepared
- pipeline is reproducible

---

## SAT-081 — Implement SAR Water/Flood Detection

**Priority:** P0

### Acceptance Criteria

- returns flood/water mask
- test demo produces credible output

---

## SAT-082 — Implement Optical Reliability Decision

**Priority:** P0

### Acceptance Criteria

When optical quality is poor:

- planner receives warning
- SAR can be preferred for flood task
- reason shown in execution trace

---

## SAT-083 — Calculate Flood Area

**Priority:** P0

### Acceptance Criteria

- flood polygons created
- affected area returned

---

# EPIC 10 — Environmental Change

## SAT-090 — Implement Vegetation Analysis

**Priority:** P1

### Possible methods

- NDVI
- vegetation segmentation

### Acceptance Criteria

- produces vegetation mask/index
- supports temporal comparison

---

## SAT-091 — Vegetation Loss Statistics

**Priority:** P1

---

# EPIC 11 — Remote-Sensing VQA

## SAT-100 — Select Base VLM

**Priority:** P0

### Acceptance Criteria

Document:

- license
- input limits
- hardware requirements
- baseline performance

---

## SAT-101 — Create Remote-Sensing VQA Dataset Pipeline

**Priority:** P1

### Acceptance Criteria

- dataset preprocessing reproducible
- train/validation split documented

---

## SAT-102 — Fine-Tune / Adapt VLM

**Priority:** P1

### Suggested technique

- LoRA / PEFT

### Acceptance Criteria

- saved adapter/model version
- evaluation against baseline
- inference integrated

---

## SAT-103 — Integrate VQA Tool

**Priority:** P0/P1

### Acceptance Criteria

- planner can invoke VQA
- response identifies model version
- VQA not used for unsupported quantitative calculation

---

# EPIC 12 — Evidence & Confidence

## SAT-110 — Define Confidence Contract

**Priority:** P0

### Acceptance Criteria

Each specialist returns:

- score
- score type
- warnings
- quality metadata

---

## SAT-111 — Implement Evidence Gate

**Priority:** P0

### Outputs

- high
- medium
- low
- insufficient

### Acceptance Criteria

Low evidence does not become confident factual language.

---

## SAT-112 — Implement Cross-Modal Evidence Fusion

**Priority:** P1

### Inputs

- optical score
- SAR score
- spatial overlap
- quality penalties

### Acceptance Criteria

- fusion formula documented
- not described as scientifically calibrated unless validated

---

# EPIC 13 — Response Generation

## SAT-120 — Build Structured Result Schema

**Priority:** P0

### Required fields

- answer
- confidence
- statistics
- evidence
- warnings
- layers
- execution trace

---

## SAT-121 — Implement Grounded Natural-Language Response

**Priority:** P0

### Acceptance Criteria

- numerical claims come from structured tool outputs
- warnings included
- uncertainty represented

---

# EPIC 14 — Map & Visualization

## SAT-130 — Integrate Map Component

**Priority:** P0

### Acceptance Criteria

- base map renders
- raster result layers visible
- polygons visible

---

## SAT-131 — Add Layer Controls

**Priority:** P0

### Controls

- show/hide
- opacity
- zoom to layer

---

## SAT-132 — Build Before/After Slider

**Priority:** P0

### Acceptance Criteria

- two temporal images can be visually compared

---

## SAT-133 — Add Change Mask Overlay

**Priority:** P0

---

## SAT-134 — Add Polygon Hover/Click Stats

**Priority:** P1

---

# EPIC 15 — Result Interface

## SAT-140 — Build Answer Card

**Priority:** P0

---

## SAT-141 — Build Statistics Cards

**Priority:** P0

Must support:

- % change
- area
- confidence

---

## SAT-142 — Build Confidence Card

**Priority:** P0

### Acceptance Criteria

- confidence label
- score
- explanation/warnings

---

## SAT-143 — Build Evidence Panel

**Priority:** P0

Displays:

- sources
- dates
- sensor
- method
- spatial evidence
- warnings

---

# EPIC 16 — Agent Execution Trace

## SAT-150 — Implement Analysis Event Log

**Priority:** P0

### Event types

- intent_detected
- input_validated
- plan_created
- model_selected
- preprocessing_started
- model_completed
- geo_processing_completed
- evidence_validated
- response_generated

---

## SAT-151 — Build Agent Trace UI

**Priority:** P0

### Acceptance Criteria

- structured steps displayed
- current step highlighted
- completed steps marked
- no private chain-of-thought displayed

---

# EPIC 17 — Async Processing

## SAT-160 — Add Analysis Job Queue

**Priority:** P0/P1

### Acceptance Criteria

- heavy jobs don't block API
- status stored

---

## SAT-161 — Implement Job Status Endpoint

**Priority:** P0

---

## SAT-162 — Add Live Progress Updates

**Priority:** P1

Preferred:

- SSE

Fallback:

- polling

---

# EPIC 18 — History & Persistence

## SAT-170 — Persist Analysis Sessions

**Priority:** P1

---

## SAT-171 — Build History UI

**Priority:** P1

---

## SAT-172 — Reopen Previous Analysis

**Priority:** P1

---

# EPIC 19 — Export

## SAT-180 — Export Result JSON

**Priority:** P0

---

## SAT-181 — Export GeoJSON

**Priority:** P1

---

## SAT-182 — Export PDF Report

**Priority:** P1

---

# EPIC 20 — Security

## SAT-190 — Add API Rate Limiting

**Priority:** P0

---

## SAT-191 — Add Upload Limits

**Priority:** P0

Acceptance:

- max bytes
- max raster dimensions
- max pixel count

---

## SAT-192 — Protect Storage Objects

**Priority:** P0

Acceptance:

- private bucket
- signed URLs
- ownership checks

---

## SAT-193 — Add Audit Logs

**Priority:** P1

---

## SAT-194 — Add Secret Scanning Checklist

**Priority:** P0

---

# EPIC 21 — Testing

## SAT-200 — Unit Tests for Metadata Extraction

**Priority:** P0

---

## SAT-201 — Unit Tests for Compatibility Checks

**Priority:** P0

---

## SAT-202 — Unit Tests for Area Calculation

**Priority:** P0

---

## SAT-203 — Planner Validation Tests

**Priority:** P0

Cases:

- unknown tool
- missing dataset
- invalid dependency
- unauthorized dataset

---

## SAT-204 — End-to-End Urban Change Test

**Priority:** P0

Flow:

```text
Upload 2 optical rasters
→ ask urban change question
→ plan
→ run
→ map
→ stats
→ confidence
```

---

## SAT-205 — End-to-End SAR Flood Test

**Priority:** P0

---

## SAT-206 — Low-Evidence Test

**Priority:** P0

Acceptance:

- result becomes low/insufficient confidence
- system does not overclaim

---

# EPIC 22 — SIH Demo Preparation

## SAT-220 — Prepare Urban Change Demo Dataset

**Priority:** P0

---

## SAT-221 — Prepare Flood/SAR Demo Dataset

**Priority:** P0

---

## SAT-222 — Prepare Environmental Demo Dataset

**Priority:** P1

---

## SAT-223 — Add Demo Query Presets

**Priority:** P0

Example:

```text
Show urban expansion between these two dates.
```

---

## SAT-224 — Build Demo Reset Action

**Priority:** P0

Acceptance:

- restores known clean demo state quickly

---

## SAT-225 — Add Demo Failure Fallback

**Priority:** P0

Prepare:

- local cached sample output
- screenshots
- result JSON
- offline explanation

This should be backup only, not fake a live result.

---

# EPIC 23 — Performance

## SAT-230 — Cache Raster Previews

**Priority:** P1

---

## SAT-231 — Cache Preprocessed Demo Inputs

**Priority:** P0

This reduces judging-time latency.

---

## SAT-232 — Record Stage Timing

**Priority:** P1

---

# EPIC 24 — Documentation

## SAT-240 — Write Local Setup Guide

**Priority:** P0

---

## SAT-241 — Write Model Registry Guide

**Priority:** P1

---

## SAT-242 — Write Demo Runbook

**Priority:** P0

Include:

- startup commands
- sample login
- demo datasets
- query sequence
- expected outputs
- recovery steps

---

# 25. Suggested Build Order

Do not start every epic together.

## Phase 1 — Foundation

```text
SAT-001
SAT-003
SAT-010
SAT-020
SAT-021
SAT-022
SAT-040
```

## Phase 2 — GIS Core

```text
SAT-030
SAT-031
SAT-032
SAT-060
SAT-061
SAT-062
SAT-072
SAT-073
```

## Phase 3 — Agent Core

```text
SAT-042
SAT-050
SAT-051
SAT-052
SAT-053
SAT-120
```

## Phase 4 — Main AI Demo

```text
SAT-070
SAT-071
SAT-081
SAT-082
SAT-083
```

## Phase 5 — Trust Layer

```text
SAT-110
SAT-111
SAT-121
SAT-150
SAT-151
```

## Phase 6 — UI Demo

```text
SAT-130
SAT-131
SAT-132
SAT-133
SAT-140
SAT-141
SAT-142
SAT-143
```

## Phase 7 — Testing

```text
SAT-200
SAT-201
SAT-202
SAT-203
SAT-204
SAT-205
SAT-206
```

## Phase 8 — Polish

P1 tickets only after P0 is stable.

---

# 26. MVP Definition of Done

The P0 release is done when:

- [ ] user can authenticate
- [ ] user can upload satellite data
- [ ] metadata is extracted
- [ ] two rasters can be compatibility-checked
- [ ] user can ask natural-language query
- [ ] intent is identified
- [ ] task plan is generated and validated
- [ ] correct specialist tool is selected
- [ ] urban change flow works
- [ ] SAR flood flow works
- [ ] area/statistics are computed
- [ ] map layer renders
- [ ] confidence/evidence shown
- [ ] agent execution trace shown
- [ ] low-evidence case handled safely
- [ ] at least 2 end-to-end demo scenarios are stable

---

# 27. Development Rule

> **A feature is not “done” when the model runs. It is done when the user can see a correct, geospatially aligned, explainable result end-to-end.**

---

# v3 Completed Integration Tickets

- [x] Natural-language vision-question routing
- [x] Hinglish flood query variants
- [x] Target-object extraction for grounding/count queries
- [x] TEOChat service adapter + bridge
- [x] Open-CD service adapter + bridge
- [x] segment-geospatial/SamGeo text-segmentation adapter
- [x] Transparent specialist fallbacks
- [x] Specialist health status in frontend Runtime panel
- [x] 24-case natural-language regression suite
- [x] 7-route E2E orchestration test matrix

# v3.1 Completed / Added Tickets

- [x] 59-check natural-language regression suite
- [x] SARChat sensor-aware semantic VQA adapter
- [x] LRS-VQA size-aware VQA adapter
- [x] TerraMind-compatible optical+SAR fusion adapter
- [x] Optical+SAR natural-language intent
- [x] Cross-modal input modality + overlap validation
- [x] 13-route E2E orchestration matrix
- [x] Runtime health UI for large-RSI VQA and multimodal fusion

# v4 Completed Trust Tickets

- [x] Reject unsupported forecasting/live-alert/impact queries
- [x] Add result provenance contract
- [x] Add operational confidence breakdown
- [x] Display fallback/model-backed status in frontend
- [x] Prevent duplicate multimodal specialist inference
- [x] Add trust-contract automated tests

