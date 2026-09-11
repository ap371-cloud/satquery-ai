# SatQuery AI Frontend v5

The main screen keeps a clean two-column research-demo workflow: ask a question on
the left, read the evidence-backed answer and trace on the right, with a grounded
evidence/provenance section and analysis history below.

## Hero workflow

```text
Question                           Final Answer
Parsed location / dates            Execution Trace
Satellite input / auto retrieval   Interactive Map / Evidence Image
Earlier + later imagery            GeoJSON / image export
Analyze                            Confidence / warnings
Sample queries
```

## Branding

The user-facing interface is branded only as **SatQuery AI**. The optional
upstream agent bridge is described generically as an external agent bridge in
the UI. Third-party attribution stays in project documentation/code, not in the
hero identity.

## v5 design system

- Dark "aurora" hero panel with gradient glows, glass capability chips and a
  gradient wordmark (`AI`).
- Larger, readable type (10–16 px) instead of the previous 7–11 px micro-type.
- Rounded 12–16 px surfaces, layered soft shadows and hover elevation.
- Dark satellite-style canvases behind imagery inputs/outputs with blur-glass
  overlays and pill metadata.
- Gradient primary buttons with a swipe-glow hover effect.
- macOS-style terminal trace (red/yellow/green toolbar dots, glowing step icons).
- Segmented-control output tabs and gradient confidence bars.
- Favicon + Inter font + dark `theme-color` metadata.

## Added in v5

- Optical + SAR joint-analysis example auto-selects the overlapping Assam
  optical + SAR demo pair.
- Hero capability chips surface sensor-aware routing, evidence-first answers and
  optical + SAR fusion.
- Interactive MapLibre evidence map retained with the matching evidence UI.

## Retained behaviors

- query context chips (location, dates, sensor),
- no-upload automatic Sentinel retrieval state,
- correct earlier/later temporal labels,
- pretrained-model vs adaptive-fallback status,
- synthetic-demo watermark,
- flood legend,
- operational-confidence wording,
- source/geospatial evidence cards.
