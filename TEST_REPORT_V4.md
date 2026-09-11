# SatQuery AI v4 — Final Automated Test Report

## Result

**All automated backend/routing/trust tests pass.**

- Python compile: **PASS (17 files)**
- Natural-language parser: **65/65 PASS**
- E2E routing matrix: **14/14 PASS**
- Assam temporal flood smoke test: **PASS**
- Trust/provenance contract: **PASS**

## Natural-language coverage

Includes English, Hinglish and Hindi variants for:
- temporal flood analysis
- urban/change detection
- vegetation loss
- single-image EO vision questions
- temporal visual Q&A
- text-prompt object grounding/counting
- optical + SAR routing
- unsupported forecasting / live-alert / impact questions

The parser now explicitly rejects unsupported capabilities rather than silently returning image statistics.

## E2E routes validated

1. Assam July→August temporal SAR flood
2. local change-detection fallback
3. transparent offline vision fallback
4. TEOChat semantic vision contract
5. SamGeo text-grounding contract
6. Open-CD trained change contract
7. temporal VLM route
8. vegetation temporal workflow
9. single-scene SAR flood
10. wrong-location rejection
11. SAR semantic VQA routing contract
12. optical + SAR fusion routing contract
13. large-RSI routing contract
14. unsupported future-forecast rejection

## Trust contract validated

Every completed result now includes:
- `provenance`
- actual method/model display
- whether fallback was used
- input source metadata
- `confidence_breakdown`
- explicit note that operational confidence is not calibrated scientific probability

## Assam smoke-test result

The bundled geo-correct synthetic Assam demo produced:

- probable new inundation: **491.3258 km²**
- persistent water: **237.9901 km²**
- operational confidence: **79%**
- GeoJSON features: **2**

These values are only for the bundled synthetic demo and must not be presented as real July/August 2025 Assam flood measurements.

## External specialist note

Heavy checkpoint accuracy is not asserted by these tests. The E2E matrix uses service doubles to validate integration contracts for optional isolated model services. The core deterministic GIS/fallback paths execute locally.

For the SIH MVP, the recommended real specialists are limited to:
- TEOChat
- Open-CD
- segment-geospatial / SamGeo
- Sentinel Flood Mapper
